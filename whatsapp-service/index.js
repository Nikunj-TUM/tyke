const { Client, LocalAuth } = require('whatsapp-web.js');
const amqp = require('amqplib');
const qrcode = require('qrcode-terminal');
const QRCode = require('qrcode');
const express = require('express');

// Configuration
const RABBITMQ_URL = `amqp://${process.env.RABBITMQ_USER || 'guest'}:${process.env.RABBITMQ_PASS || 'guest'}@${process.env.RABBITMQ_HOST || 'rabbitmq'}:5672`;
const MESSAGE_QUEUE = process.env.MESSAGE_QUEUE || 'whatsapp_messages';
const STATUS_QUEUE = process.env.STATUS_QUEUE || 'whatsapp_status';

// Express app for health checks and QR code display
const app = express();
app.use(express.json());

let currentQR = null;
let isReady = false;
let clientInfo = null;
let initializationError = null;

// Initialize WhatsApp client
console.log('Creating WhatsApp client...');
const whatsappClient = new Client({
    authStrategy: new LocalAuth({
        dataPath: '/app/.wwebjs_auth'
    }),
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu',
            '--disable-extensions'
        ],
        executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/chromium-browser'
    }
});

// WhatsApp event handlers
whatsappClient.on('qr', (qr) => {
    console.log('QR Code received, scan to authenticate:');
    qrcode.generate(qr, { small: true });
    currentQR = qr;
    isReady = false;
    initializationError = null;
    
    // Publish QR code to status queue
    publishStatus({
        status: 'qr_code',
        qr_code: qr,
        message: 'Scan QR code to authenticate'
    });
});

whatsappClient.on('authenticated', () => {
    console.log('WhatsApp authenticated successfully');
    publishStatus({
        status: 'authenticated',
        message: 'WhatsApp authenticated successfully'
    });
});

whatsappClient.on('ready', async () => {
    console.log('WhatsApp client is ready!');
    currentQR = null;
    isReady = true;
    initializationError = null;
    
    try {
        const info = whatsappClient.info;
        clientInfo = {
            wid: info.wid._serialized,
            phone: info.wid.user,
            name: info.pushname,
            platform: info.platform
        };
        console.log('Connected as:', clientInfo);
        
        publishStatus({
            status: 'ready',
            message: 'WhatsApp client is ready',
            client_info: clientInfo
        });
    } catch (error) {
        console.error('Error getting client info:', error);
    }
});

whatsappClient.on('disconnected', (reason) => {
    console.log('WhatsApp client disconnected:', reason);
    isReady = false;
    clientInfo = null;
    
    publishStatus({
        status: 'disconnected',
        message: `WhatsApp client disconnected: ${reason}`
    });
});

whatsappClient.on('auth_failure', (msg) => {
    console.error('Authentication failure:', msg);
    initializationError = msg;
    
    publishStatus({
        status: 'auth_failure',
        message: `Authentication failed: ${msg}`
    });
});

// RabbitMQ connection and channel
let rabbitConnection = null;
let rabbitChannel = null;

async function connectRabbitMQ() {
    try {
        console.log('Connecting to RabbitMQ...');
        rabbitConnection = await amqp.connect(RABBITMQ_URL);
        rabbitChannel = await rabbitConnection.createChannel();
        
        await rabbitChannel.assertQueue(MESSAGE_QUEUE, { durable: true });
        await rabbitChannel.assertQueue(STATUS_QUEUE, { durable: true });
        
        console.log(`Connected to RabbitMQ. Listening on queue: ${MESSAGE_QUEUE}`);
        return true;
    } catch (error) {
        console.error('Failed to connect to RabbitMQ:', error);
        return false;
    }
}

function publishStatus(statusData) {
    if (rabbitChannel) {
        try {
            rabbitChannel.sendToQueue(
                STATUS_QUEUE,
                Buffer.from(JSON.stringify({
                    timestamp: new Date().toISOString(),
                    ...statusData
                })),
                { persistent: true }
            );
        } catch (error) {
            console.error('Error publishing status:', error);
        }
    }
}

// Health check endpoint
app.get('/health', (req, res) => {
    res.json({
        status: isReady ? 'ready' : (currentQR ? 'awaiting_qr_scan' : 'initializing'),
        whatsapp_connected: isReady,
        qr_available: !!currentQR,
        rabbitmq_connected: !!rabbitChannel,
        client_info: clientInfo,
        error: initializationError
    });
});

// QR code endpoint (for initial setup)
app.get('/qr', async (req, res) => {
    if (currentQR) {
        // Return QR as image
        try {
            const qrImage = await QRCode.toDataURL(currentQR);
            res.json({
                qr_code: currentQR,
                qr_image: qrImage,
                message: 'Scan this QR code with WhatsApp'
            });
        } catch (error) {
            res.type('text/plain').send(currentQR);
        }
    } else if (isReady) {
        res.json({ 
            status: 'connected',
            message: 'Already authenticated',
            client_info: clientInfo
        });
    } else {
        res.status(404).json({ message: 'QR not available yet. Please wait...' });
    }
});

// Status endpoint
app.get('/status', (req, res) => {
    res.json({
        connected: isReady,
        qr_pending: !!currentQR,
        client_info: clientInfo,
        error: initializationError
    });
});

// Start Express server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`WhatsApp service web interface running on port ${PORT}`);
});

// Initialize services
async function initialize() {
    // Connect to RabbitMQ first
    const rabbitConnected = await connectRabbitMQ();
    
    if (!rabbitConnected) {
        console.error('Failed to connect to RabbitMQ. Retrying in 5 seconds...');
        setTimeout(initialize, 5000);
        return;
    }
    
    // Start message processor
    processMessages();
    
    // Initialize WhatsApp client
    console.log('Initializing WhatsApp client...');
    try {
        whatsappClient.initialize();
    } catch (error) {
        console.error('Error initializing WhatsApp client:', error);
        initializationError = error.message;
    }
}

// RabbitMQ message processor
async function processMessages() {
    try {
        console.log(`Waiting for messages in queue: ${MESSAGE_QUEUE}`);
        
        rabbitChannel.consume(MESSAGE_QUEUE, async (msg) => {
            if (msg !== null) {
                try {
                    const messageData = JSON.parse(msg.content.toString());
                    console.log('Received message:', messageData);
                    
                    const { phone_number, message, contact_name, message_id } = messageData;
                    
                    if (!isReady) {
                        console.error('WhatsApp client not ready, rejecting message');
                        publishStatus({
                            status: 'message_failed',
                            message_id: message_id,
                            error: 'WhatsApp client not ready',
                            phone_number: phone_number
                        });
                        rabbitChannel.nack(msg, false, true); // Requeue
                        return;
                    }
                    
                    // Format phone number (ensure it includes country code)
                    // Example: +919876543210 -> 919876543210@c.us
                    let formattedNumber = phone_number.replace(/[^0-9]/g, '');
                    
                    // If number doesn't start with country code, might need handling
                    if (!formattedNumber.startsWith('91') && formattedNumber.length === 10) {
                        // Assume Indian number if 10 digits
                        formattedNumber = '91' + formattedNumber;
                    }
                    
                    formattedNumber += '@c.us';
                    
                    console.log(`Sending message to ${formattedNumber}...`);
                    
                    // Send WhatsApp message
                    const result = await whatsappClient.sendMessage(formattedNumber, message);
                    
                    console.log(`Message sent successfully to ${contact_name || phone_number}`);
                    
                    // Publish success status
                    publishStatus({
                        status: 'message_sent',
                        message_id: message_id,
                        phone_number: phone_number,
                        contact_name: contact_name,
                        sent_at: new Date().toISOString()
                    });
                    
                    // Acknowledge message
                    rabbitChannel.ack(msg);
                    
                    // Small delay to avoid rate limiting
                    await new Promise(resolve => setTimeout(resolve, 1000));
                    
                } catch (error) {
                    console.error('Error processing message:', error);
                    
                    const messageData = JSON.parse(msg.content.toString());
                    publishStatus({
                        status: 'message_failed',
                        message_id: messageData.message_id,
                        phone_number: messageData.phone_number,
                        error: error.message
                    });
                    
                    // Reject and don't requeue on processing error
                    rabbitChannel.nack(msg, false, false);
                }
            }
        }, {
            noAck: false // Manual acknowledgment
        });
        
    } catch (error) {
        console.error('Error in message processor:', error);
        // Retry after delay
        setTimeout(processMessages, 5000);
    }
}

// Graceful shutdown
process.on('SIGINT', async () => {
    console.log('Shutting down gracefully...');
    try {
        if (whatsappClient) {
            await whatsappClient.destroy();
        }
        if (rabbitChannel) {
            await rabbitChannel.close();
        }
        if (rabbitConnection) {
            await rabbitConnection.close();
        }
    } catch (error) {
        console.error('Error during shutdown:', error);
    }
    process.exit(0);
});

process.on('SIGTERM', async () => {
    console.log('Received SIGTERM, shutting down...');
    try {
        if (whatsappClient) {
            await whatsappClient.destroy();
        }
        if (rabbitChannel) {
            await rabbitChannel.close();
        }
        if (rabbitConnection) {
            await rabbitConnection.close();
        }
    } catch (error) {
        console.error('Error during shutdown:', error);
    }
    process.exit(0);
});

// Handle uncaught errors
process.on('uncaughtException', (error) => {
    console.error('Uncaught exception:', error);
});

process.on('unhandledRejection', (error) => {
    console.error('Unhandled rejection:', error);
});

// Start initialization
initialize();

