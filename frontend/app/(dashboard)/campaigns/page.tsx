"use client";

import { useEffect, useState } from "react";
import apiClient from "@/lib/api-client";
import { Plus, Play, Pause, BarChart3, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { CAMPAIGN_STATUSES } from "@/lib/constants";
import { Skeleton } from "@/components/ui/skeleton";
import Link from "next/link";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

interface Campaign {
  id: number;
  name: string;
  status: string;
  whatsapp_instance_name: string;
  total_contacts: number;
  messages_sent: number;
  messages_failed: number;
  messages_pending: number;
  created_at: string;
}

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [campaignToDelete, setCampaignToDelete] = useState<number | null>(null);

  useEffect(() => {
    fetchCampaigns();
  }, []);

  const fetchCampaigns = async () => {
    try {
      setIsLoading(true);
      const response = await apiClient.getCampaigns();
      setCampaigns(response.data);
    } catch (error) {
      console.error("Error fetching campaigns:", error);
      toast.error("Failed to fetch campaigns");
    } finally {
      setIsLoading(false);
    }
  };

  const handleStartCampaign = async (campaignId: number) => {
    setActionLoading(campaignId);
    try {
      await apiClient.startCampaign(campaignId);
      toast.success("Campaign started successfully");
      fetchCampaigns();
    } catch (error: any) {
      console.error("Error starting campaign:", error);
      toast.error(error.response?.data?.detail || "Failed to start campaign");
    } finally {
      setActionLoading(null);
    }
  };

  const handlePauseCampaign = async (campaignId: number) => {
    setActionLoading(campaignId);
    try {
      await apiClient.pauseCampaign(campaignId);
      toast.success("Campaign paused successfully");
      fetchCampaigns();
    } catch (error: any) {
      console.error("Error pausing campaign:", error);
      toast.error(error.response?.data?.detail || "Failed to pause campaign");
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteCampaign = async () => {
    if (!campaignToDelete) return;
    
    try {
      await apiClient.deleteCampaign(campaignToDelete);
      toast.success("Campaign deleted successfully");
      setCampaignToDelete(null);
      setDeleteDialogOpen(false);
      fetchCampaigns();
    } catch (error: any) {
      console.error("Error deleting campaign:", error);
      toast.error(error.response?.data?.detail || "Failed to delete campaign");
    }
  };

  const getStatusBadge = (status: string) => {
    const statusConfig = CAMPAIGN_STATUSES.find((s) => s.value === status) || CAMPAIGN_STATUSES[0];
    return (
      <Badge variant="outline" className={statusConfig.color}>
        {statusConfig.label}
      </Badge>
    );
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-full" />
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-48" />
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
          <h1 className="text-3xl font-bold tracking-tight">Campaigns</h1>
          <p className="text-muted-foreground">Manage WhatsApp outreach campaigns</p>
        </div>
        <Button asChild>
          <Link href="/campaigns/create">
            <Plus className="mr-2 h-4 w-4" />
          Create Campaign
          </Link>
        </Button>
      </div>

      {/* Campaigns List */}
      {campaigns.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <BarChart3 className="h-16 w-16 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No campaigns yet</h3>
            <p className="text-muted-foreground text-center mb-6 max-w-md">
              Create your first campaign to start messaging your contacts
            </p>
            <Button asChild>
              <Link href="/campaigns/create">
                <Plus className="mr-2 h-4 w-4" />
                Create Campaign
              </Link>
            </Button>
          </CardContent>
        </Card>
        ) : (
        <div className="space-y-4">
          {campaigns.map((campaign) => {
            const progressPercent = campaign.total_contacts > 0
              ? (campaign.messages_sent / campaign.total_contacts) * 100
              : 0;

            return (
              <Card key={campaign.id} className="hover:shadow-md transition-shadow">
                <CardContent className="p-6">
                <div className="flex items-start justify-between">
                    <div className="flex-1 space-y-4">
                      <div>
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="text-xl font-semibold">{campaign.name}</h3>
                          {getStatusBadge(campaign.status)}
                        </div>
                        <p className="text-sm text-muted-foreground">
                          via {campaign.whatsapp_instance_name}
                        </p>
                      </div>

                      <div className="grid grid-cols-4 gap-4">
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">Total Contacts</p>
                          <p className="text-2xl font-bold">{campaign.total_contacts}</p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">Sent</p>
                          <p className="text-2xl font-bold text-green-600">
                            {campaign.messages_sent}
                          </p>
                      </div>
                      <div>
                          <p className="text-xs text-muted-foreground mb-1">Pending</p>
                          <p className="text-2xl font-bold text-blue-600">
                            {campaign.messages_pending}
                          </p>
                      </div>
                      <div>
                          <p className="text-xs text-muted-foreground mb-1">Failed</p>
                          <p className="text-2xl font-bold text-red-600">
                            {campaign.messages_failed}
                          </p>
                        </div>
                      </div>

                      <div className="space-y-2">
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">Progress</span>
                          <span className="font-medium">{progressPercent.toFixed(1)}%</span>
                      </div>
                        <Progress value={progressPercent} className="h-2" />
                    </div>
                  </div>

                    <div className="flex gap-2 ml-6">
                      {campaign.status === "running" && (
                        <Button
                          variant="outline"
                          size="icon"
                        onClick={() => handlePauseCampaign(campaign.id)}
                          disabled={actionLoading === campaign.id}
                        title="Pause Campaign"
                      >
                          <Pause className="h-4 w-4" />
                        </Button>
                    )}
                      {(campaign.status === "draft" || campaign.status === "paused") && (
                        <Button
                          variant="outline"
                          size="icon"
                        onClick={() => handleStartCampaign(campaign.id)}
                          disabled={actionLoading === campaign.id}
                        title="Start Campaign"
                      >
                          <Play className="h-4 w-4" />
                        </Button>
                    )}
                      <Button
                        variant="outline"
                        size="icon"
                        asChild
                      title="View Analytics"
                    >
                        <Link href={`/campaigns/${campaign.id}`}>
                          <BarChart3 className="h-4 w-4" />
                        </Link>
                      </Button>
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={() => {
                          setCampaignToDelete(campaign.id);
                          setDeleteDialogOpen(true);
                        }}
                        className="text-destructive hover:text-destructive"
                        title="Delete Campaign"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
          </div>
        )}

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. This will permanently delete the campaign
              and all associated data.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setCampaignToDelete(null)}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteCampaign} className="bg-destructive hover:bg-destructive/90">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
