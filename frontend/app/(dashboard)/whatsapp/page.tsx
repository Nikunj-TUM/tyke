"use client";

import { useEffect, useState } from "react";
import apiClient from "@/lib/api-client";
import { Plus, QrCode, CheckCircle, XCircle, RefreshCw, MessageSquare, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { whatsappInstanceSchema, type WhatsAppInstanceFormData } from "@/lib/form-schemas";
import { Skeleton } from "@/components/ui/skeleton";

interface WhatsAppInstance {
  id: number;
  name: string;
  phone_number: string;
  is_authenticated: boolean;
  is_active: boolean;
  messages_sent_today: number;
  daily_message_limit: number;
}

export default function WhatsAppPage() {
  const [instances, setInstances] = useState<WhatsAppInstance[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedInstance, setSelectedInstance] = useState<number | null>(null);
  const [qrData, setQrData] = useState<any>(null);
  const [showQRModal, setShowQRModal] = useState(false);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<any>({
    defaultValues: {
      name: "",
      phone_number: "",
      daily_message_limit: 1000,
    },
  });

  useEffect(() => {
    fetchInstances();
  }, []);

  const fetchInstances = async () => {
    try {
      setIsLoading(true);
      const response = await apiClient.getWhatsAppInstances();
      setInstances(response.data);
    } catch (error) {
      console.error("Error fetching instances:", error);
      toast.error("Failed to fetch WhatsApp instances");
    } finally {
      setIsLoading(false);
    }
  };

  const handleShowQR = async (instanceId: number) => {
    try {
      const response = await apiClient.getWhatsAppInstanceQR(instanceId);
      setQrData(response.data);
      setSelectedInstance(instanceId);
      setShowQRModal(true);
    } catch (error) {
      console.error("Error fetching QR code:", error);
      toast.error("Failed to get QR code");
    }
  };

  const onSubmit = async (data: WhatsAppInstanceFormData) => {
    setIsSubmitting(true);
    try {
      await apiClient.createWhatsAppInstance(data);
      toast.success("WhatsApp instance created successfully");
      setShowAddDialog(false);
      reset();
      fetchInstances();
    } catch (error: any) {
      console.error("Error creating instance:", error);
      toast.error(error.response?.data?.detail || "Failed to create instance");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-full" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-64" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">WhatsApp Instances</h1>
          <p className="text-muted-foreground">Manage your WhatsApp phone numbers</p>
        </div>
        <Button onClick={() => setShowAddDialog(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Phone Number
        </Button>
      </div>

      {/* Instances Grid */}
      {instances.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <MessageSquare className="h-16 w-16 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No WhatsApp instances</h3>
            <p className="text-muted-foreground text-center mb-6 max-w-md">
              Get started by adding your first WhatsApp phone number to begin messaging your contacts
            </p>
            <Button onClick={() => setShowAddDialog(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Add Phone Number
            </Button>
          </CardContent>
        </Card>
        ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {instances.map((instance) => {
            const usagePercent = (instance.messages_sent_today / instance.daily_message_limit) * 100;

            return (
              <Card key={instance.id} className="hover:shadow-lg transition-shadow">
                <CardHeader>
              <div className="flex items-start justify-between">
                <div className="flex-1">
                      <CardTitle className="text-lg">{instance.name}</CardTitle>
                      <CardDescription className="mt-1">{instance.phone_number}</CardDescription>
                </div>
                {instance.is_authenticated ? (
                      <Badge variant="default" className="bg-green-600">
                        <CheckCircle className="mr-1 h-3 w-3" />
                        Connected
                      </Badge>
                ) : (
                      <Badge variant="secondary">
                        <XCircle className="mr-1 h-3 w-3" />
                        Disconnected
                      </Badge>
                )}
              </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Messages Today</span>
                      <span className="font-medium">
                        {instance.messages_sent_today} / {instance.daily_message_limit}
                  </span>
                </div>
                    <Progress value={usagePercent} className="h-2" />
              </div>

                  <div className="flex gap-2">
                {!instance.is_authenticated && (
                      <Button
                        variant="outline"
                        size="sm"
                    onClick={() => handleShowQR(instance.id)}
                        className="flex-1"
                  >
                        <QrCode className="mr-2 h-4 w-4" />
                        Connect
                      </Button>
                )}
                    <Button variant="outline" size="sm" className="flex-1">
                  Settings
                    </Button>
              </div>
                </CardContent>
              </Card>
            );
          })}
            </div>
        )}

      {/* QR Code Modal */}
      <Dialog open={showQRModal} onOpenChange={setShowQRModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Scan QR Code</DialogTitle>
            <DialogDescription>
              Scan this QR code with WhatsApp to authenticate
            </DialogDescription>
          </DialogHeader>
            
          {qrData?.is_authenticated ? (
            <div className="flex flex-col items-center py-8">
              <CheckCircle className="h-16 w-16 text-green-600 mb-4" />
              <p className="text-green-600 font-medium">Already authenticated!</p>
              </div>
          ) : qrData?.qr_image ? (
            <div className="flex flex-col items-center space-y-4">
              <div className="p-4 bg-white rounded-lg">
                  <img 
                    src={qrData.qr_image} 
                    alt="QR Code" 
                    className="w-64 h-64"
                  />
                </div>
              <p className="text-sm text-muted-foreground text-center">
                Open WhatsApp on your phone and scan this QR code
                </p>
                {qrData.expires_at && (
                <p className="text-xs text-muted-foreground">
                  Code expires in 5 minutes
                  </p>
                )}
              </div>
            ) : (
            <div className="flex flex-col items-center py-8">
              <Loader2 className="h-16 w-16 text-muted-foreground animate-spin mb-4" />
              <p className="text-muted-foreground">Generating QR code...</p>
              </div>
            )}
            
          <DialogFooter>
            <Button onClick={() => setShowQRModal(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add Instance Dialog */}
      <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add WhatsApp Instance</DialogTitle>
            <DialogDescription>
              Create a new WhatsApp phone number connection
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)}>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="name">Instance Name *</Label>
                <Input
                  id="name"
                  placeholder="Main WhatsApp"
                  {...register("name")}
                  disabled={isSubmitting}
                />
                {errors.name && (
                  <p className="text-sm text-destructive">{String(errors.name.message || "")}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="phone_number">Phone Number *</Label>
                <Input
                  id="phone_number"
                  type="tel"
                  placeholder="+919876543210"
                  {...register("phone_number")}
                  disabled={isSubmitting}
                />
                {errors.phone_number && (
                  <p className="text-sm text-destructive">{String(errors.phone_number.message || "")}</p>
                )}
                <p className="text-xs text-muted-foreground">
                  Include country code (e.g., +91 for India)
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="daily_message_limit">Daily Message Limit</Label>
                <Input
                  id="daily_message_limit"
                  type="number"
                  min="1"
                  max="10000"
                  {...register("daily_message_limit", { valueAsNumber: true })}
                  disabled={isSubmitting}
                />
                {errors.daily_message_limit && (
                  <p className="text-sm text-destructive">{String(errors.daily_message_limit.message || "")}</p>
                )}
                <p className="text-xs text-muted-foreground">
                  Maximum messages to send per day (default: 1000)
                </p>
          </div>
        </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowAddDialog(false)}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create Instance
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
