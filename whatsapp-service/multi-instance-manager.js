/**
 * Multi-instance WhatsApp Manager
 * Manages multiple WhatsApp clients simultaneously for different organizations
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const { Pool } = require('pg');

// PostgreSQL connection pool
const pool = new Pool({
    host: process.env.POSTGRES_HOST || 'postgres',
    port: process.env.POSTGRES_PORT || 5432,
    database: process.env.POSTGRES_DB || 'infomerics',
    user: process.env.POSTGRES_USER || 'infomerics_user',
    password: process.env.POSTGRES_PASSWORD,
});

// Store for active WhatsApp clients
// Map<instanceId, { client: Client, info: Object }>
const activeClients = new Map();

// Store for pending QR codes
// Map<instanceId, qrCode>
const pendingQRCodes = new Map();

class MultiInstanceManager {
    constructor(rabbitChannel, statusQueue) {
        this.rabbitChannel = rabbitChannel;
        this.statusQueue = statusQueue;
    }

    /**
     * Fetch instances from database that need initialization
     */
    async fetchInstances() {
        try {
            const result = await pool.query(`
                SELECT 
                    id,
                    organization_id,
                    name,
                    phone_number,
                    is_authenticated,
                    is_active
                FROM whatsapp_instances
                WHERE is_active = TRUE
                ORDER BY created_at ASC
            `);
            
            return result.rows;
        } catch (error) {
            console.error('Error fetching instances from database:', error);
            return [];
        }
    }

    /**
     * Initialize a WhatsApp client for an instance
     */
    async initializeClient(instance) {
        const instanceId = instance.id;
        
        // Check if already initialized
        if (activeClients.has(instanceId)) {
            console.log(`Instance ${instanceId} already initialized`);
            return;
        }

        console.log(`Initializing WhatsApp client for instance ${instanceId} (${instance.name})`);

        const client = new Client({
            authStrategy: new LocalAuth({
                clientId: `instance-${instanceId}`,
                dataPath: `/app/.wwebjs_auth/instance-${instanceId}`
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

        // Setup event handlers
        this.setupClientEventHandlers(client, instance);

        // Store client
        activeClients.set(instanceId, {
            client: client,
            instance: instance,
            isReady: false
        });

        // Initialize client
        try {
            await client.initialize();
        } catch (error) {
            console.error(`Error initializing client for instance ${instanceId}:`, error);
            activeClients.delete(instanceId);
        }
    }

    /**
     * Setup event handlers for a WhatsApp client
     */
    setupClientEventHandlers(client, instance) {
        const instanceId = instance.id;

        client.on('qr', async (qr) => {
            console.log(`QR Code received for instance ${instanceId} (${instance.name})`);
            pendingQRCodes.set(instanceId, qr);

            // Update database with QR code
            try {
                await pool.query(`
                    UPDATE whatsapp_instances
                    SET 
                        qr_code = $1,
                        qr_expires_at = CURRENT_TIMESTAMP + INTERVAL '5 minutes',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $2
                `, [qr, instanceId]);

                // Publish status
                this.publishStatus({
                    instance_id: instanceId,
                    organization_id: instance.organization_id,
                    status: 'qr_code',
                    qr_code: qr,
                    message: `QR code for ${instance.name}`
                });
            } catch (error) {
                console.error(`Error updating QR code for instance ${instanceId}:`, error);
            }
        });

        client.on('authenticated', async () => {
            console.log(`Instance ${instanceId} authenticated successfully`);
            
            this.publishStatus({
                instance_id: instanceId,
                organization_id: instance.organization_id,
                status: 'authenticated',
                message: `Instance ${instance.name} authenticated`
            });
        });

        client.on('ready', async () => {
            console.log(`Instance ${instanceId} is ready!`);
            
            // Clear QR code
            pendingQRCodes.delete(instanceId);

            // Get client info
            try {
                const info = client.info;
                const clientInfo = {
                    wid: info.wid._serialized,
                    phone: info.wid.user,
                    name: info.pushname,
                    platform: info.platform
                };

                // Update database
                await pool.query(`
                    UPDATE whatsapp_instances
                    SET 
                        is_authenticated = TRUE,
                        qr_code = NULL,
                        qr_expires_at = NULL,
                        client_info = $1,
                        last_connected_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $2
                `, [JSON.stringify(clientInfo), instanceId]);

                // Update active clients
                const clientData = activeClients.get(instanceId);
                if (clientData) {
                    clientData.isReady = true;
                    clientData.clientInfo = clientInfo;
                }

                // Publish status
                this.publishStatus({
                    instance_id: instanceId,
                    organization_id: instance.organization_id,
                    status: 'ready',
                    message: `Instance ${instance.name} is ready`,
                    client_info: clientInfo
                });

                console.log(`Instance ${instanceId} connected as:`, clientInfo);
            } catch (error) {
                console.error(`Error getting client info for instance ${instanceId}:`, error);
            }
        });

        client.on('disconnected', async (reason) => {
            console.log(`Instance ${instanceId} disconnected:`, reason);

            // Update database
            try {
                await pool.query(`
                    UPDATE whatsapp_instances
                    SET 
                        is_authenticated = FALSE,
                        qr_code = NULL,
                        qr_expires_at = NULL,
                        last_disconnected_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $1
                `, [instanceId]);
            } catch (error) {
                console.error(`Error updating disconnected status for instance ${instanceId}:`, error);
            }

            // Update active clients
            const clientData = activeClients.get(instanceId);
            if (clientData) {
                clientData.isReady = false;
            }

            // Publish status
            this.publishStatus({
                instance_id: instanceId,
                organization_id: instance.organization_id,
                status: 'disconnected',
                message: `Instance ${instance.name} disconnected: ${reason}`
            });
        });

        client.on('auth_failure', async (msg) => {
            console.error(`Authentication failure for instance ${instanceId}:`, msg);

            // Publish status
            this.publishStatus({
                instance_id: instanceId,
                organization_id: instance.organization_id,
                status: 'auth_failure',
                message: `Authentication failed for ${instance.name}: ${msg}`
            });
        });
    }

    /**
     * Get a client by instance ID
     */
    getClient(instanceId) {
        const clientData = activeClients.get(instanceId);
        return clientData?.isReady ? clientData.client : null;
    }

    /**
     * Get QR code for an instance
     */
    getQRCode(instanceId) {
        return pendingQRCodes.get(instanceId);
    }

    /**
     * Get all active instances
     */
    getActiveInstances() {
        return Array.from(activeClients.entries()).map(([id, data]) => ({
            instance_id: id,
            organization_id: data.instance.organization_id,
            name: data.instance.name,
            phone_number: data.instance.phone_number,
            is_ready: data.isReady,
            has_qr: pendingQRCodes.has(id),
            client_info: data.clientInfo
        }));
    }

    /**
     * Send message using specific instance
     */
    async sendMessage(instanceId, phoneNumber, message) {
        const client = this.getClient(instanceId);
        
        if (!client) {
            throw new Error(`Instance ${instanceId} not ready or not found`);
        }

        // Format phone number
        let formattedNumber = phoneNumber.replace(/[^0-9]/g, '');
        
        // If number doesn't start with country code, assume Indian number
        if (!formattedNumber.startsWith('91') && formattedNumber.length === 10) {
            formattedNumber = '91' + formattedNumber;
        }
        
        formattedNumber += '@c.us';

        // Send message
        const result = await client.sendMessage(formattedNumber, message);
        
        // Increment message count in database
        try {
            await pool.query(`
                UPDATE whatsapp_instances
                SET 
                    messages_sent_today = messages_sent_today + 1,
                    last_message_sent_at = CURRENT_TIMESTAMP
                WHERE id = $1
            `, [instanceId]);
        } catch (error) {
            console.error(`Error updating message count for instance ${instanceId}:`, error);
        }

        return result;
    }

    /**
     * Poll database for new instances
     */
    async pollForNewInstances() {
        try {
            const instances = await this.fetchInstances();
            
            for (const instance of instances) {
                if (!activeClients.has(instance.id)) {
                    console.log(`Found new instance to initialize: ${instance.id} (${instance.name})`);
                    await this.initializeClient(instance);
                }
            }
        } catch (error) {
            console.error('Error polling for new instances:', error);
        }
    }

    /**
     * Destroy a client instance
     */
    async destroyClient(instanceId) {
        const clientData = activeClients.get(instanceId);
        
        if (clientData) {
            try {
                await clientData.client.destroy();
                activeClients.delete(instanceId);
                pendingQRCodes.delete(instanceId);
                console.log(`Destroyed client for instance ${instanceId}`);
                return true;
            } catch (error) {
                console.error(`Error destroying client ${instanceId}:`, error);
                return false;
            }
        }
        
        return false;
    }

    /**
     * Publish status to RabbitMQ
     */
    publishStatus(statusData) {
        if (this.rabbitChannel) {
            try {
                this.rabbitChannel.sendToQueue(
                    this.statusQueue,
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

    /**
     * Cleanup all clients
     */
    async cleanup() {
        console.log('Cleaning up all WhatsApp clients...');
        
        for (const [instanceId, clientData] of activeClients.entries()) {
            try {
                await clientData.client.destroy();
                console.log(`Destroyed client for instance ${instanceId}`);
            } catch (error) {
                console.error(`Error destroying client ${instanceId}:`, error);
            }
        }
        
        activeClients.clear();
        pendingQRCodes.clear();
        
        // Close database pool
        await pool.end();
    }
}

module.exports = MultiInstanceManager;

