"use client";

import { useEffect, useState } from "react";
import apiClient from "@/lib/api-client";
import { Plus, LayoutGrid, List } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { toast } from "sonner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DEAL_STAGES, CURRENCIES } from "@/lib/constants";
import { Skeleton } from "@/components/ui/skeleton";
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
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { dealSchema, type DealFormData } from "@/lib/form-schemas";
import { Loader2 } from "lucide-react";

interface Deal {
  id: number;
  title: string;
  description: string | null;
  stage: string;
  value: number | null;
  currency: string;
  probability: number;
  company_name: string | null;
  contact_name: string | null;
  owner_name: string | null;
  expected_close_date: string | null;
  created_at: string;
  updated_at: string;
}

export default function DealsPage() {
  const [deals, setDeals] = useState<Deal[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [view, setView] = useState<"kanban" | "table">("kanban");

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
    control,
  } = useForm<any>({
    defaultValues: {
      title: "",
      description: "",
      stage: "lead",
      value: 0,
      currency: "INR",
      probability: 0,
    },
  });

  useEffect(() => {
    fetchDeals();
  }, []);

  const fetchDeals = async () => {
    try {
      setIsLoading(true);
      // TODO: Add getDeals method to apiClient or use axios directly
      setDeals([]);
    } catch (error) {
      console.error("Error fetching deals:", error);
      toast.error("Failed to fetch deals");
    } finally {
      setIsLoading(false);
    }
  };

  const onSubmit = async (data: any) => {
    setIsSubmitting(true);
    try {
      // TODO: Add createDeal method to apiClient
      toast.success("Deal created successfully");
      setShowAddDialog(false);
      reset();
      fetchDeals();
    } catch (error: any) {
      console.error("Error creating deal:", error);
      toast.error(error.response?.data?.detail || "Failed to create deal");
    } finally {
      setIsSubmitting(false);
    }
  };

  const getStageDeals = (stage: string) => {
    return deals.filter((deal) => deal.stage === stage);
  };

  const formatCurrency = (value: number | null, currency: string) => {
    if (!value) return "—";
    const currencyObj = CURRENCIES.find((c) => c.value === currency);
    return `${currencyObj?.symbol || "₹"}${value.toLocaleString()}`;
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-full" />
        <div className="grid grid-cols-6 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-96" />
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
          <h1 className="text-3xl font-bold tracking-tight">Deals</h1>
          <p className="text-muted-foreground">Track and manage your sales pipeline</p>
        </div>
        <div className="flex items-center gap-2">
          <Tabs value={view} onValueChange={(v) => setView(v as "kanban" | "table")}>
            <TabsList>
              <TabsTrigger value="kanban">
                <LayoutGrid className="mr-2 h-4 w-4" />
                Kanban
              </TabsTrigger>
              <TabsTrigger value="table">
                <List className="mr-2 h-4 w-4" />
                Table
              </TabsTrigger>
            </TabsList>
          </Tabs>
          <Button onClick={() => setShowAddDialog(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Add Deal
          </Button>
        </div>
      </div>

      {/* Kanban View */}
      {view === "kanban" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
          {DEAL_STAGES.map((stage) => {
            const stageDeals = getStageDeals(stage.value);
            const totalValue = stageDeals.reduce((sum, deal) => sum + (deal.value || 0), 0);

            return (
              <div key={stage.value} className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-sm">{stage.label}</h3>
                    <p className="text-xs text-muted-foreground">
                      {stageDeals.length} deals • ₹{totalValue.toLocaleString()}
                    </p>
                  </div>
                </div>
                <div className="space-y-2 max-h-[calc(100vh-250px)] overflow-y-auto scrollbar-thin">
                  {stageDeals.map((deal) => (
                    <Card key={deal.id} className="cursor-pointer hover:shadow-md transition-shadow">
                      <CardContent className="p-4">
                        <h4 className="font-medium text-sm mb-2">{deal.title}</h4>
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-semibold">
                              {formatCurrency(deal.value, deal.currency)}
                            </span>
                            <Badge variant="outline" className="text-xs">
                              {deal.probability}%
                            </Badge>
                          </div>
                          {deal.company_name && (
                            <p className="text-xs text-muted-foreground truncate">
                              {deal.company_name}
                            </p>
                          )}
                          {deal.owner_name && (
                            <div className="flex items-center gap-2">
                              <Avatar className="h-5 w-5">
                                <AvatarFallback className="text-xs">
                                  {deal.owner_name[0]}
                                </AvatarFallback>
                              </Avatar>
                              <span className="text-xs text-muted-foreground truncate">
                                {deal.owner_name}
                              </span>
                            </div>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                  {stageDeals.length === 0 && (
                    <div className="text-center py-8 text-sm text-muted-foreground">
                      No deals in this stage
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Table View */}
      {view === "table" && (
        <Card>
          <CardContent className="p-6">
            <div className="text-center py-12 text-muted-foreground">
              <List className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>Table view coming soon</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Add Deal Dialog */}
      <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Create New Deal</DialogTitle>
            <DialogDescription>
              Add a new deal to your sales pipeline
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)}>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="title">Deal Title *</Label>
                <Input
                  id="title"
                  placeholder="Enterprise Plan - Acme Corp"
                  {...register("title")}
                  disabled={isSubmitting}
                />
                {errors.title && (
                  <p className="text-sm text-destructive">{String(errors.title.message || "")}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  placeholder="Deal details and notes..."
                  {...register("description")}
                  disabled={isSubmitting}
                  rows={3}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="stage">Stage *</Label>
                  <Controller
                    name="stage"
                    control={control}
                    render={({ field }) => (
                      <Select
                        onValueChange={field.onChange}
                        defaultValue={field.value}
                        disabled={isSubmitting}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select stage" />
                        </SelectTrigger>
                        <SelectContent>
                          {DEAL_STAGES.map((stage) => (
                            <SelectItem key={stage.value} value={stage.value}>
                              {stage.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="probability">Probability (%)</Label>
                  <Input
                    id="probability"
                    type="number"
                    min="0"
                    max="100"
                    {...register("probability", { valueAsNumber: true })}
                    disabled={isSubmitting}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="value">Deal Value</Label>
                  <Input
                    id="value"
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="100000"
                    {...register("value", { valueAsNumber: true })}
                    disabled={isSubmitting}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="currency">Currency</Label>
                  <Controller
                    name="currency"
                    control={control}
                    render={({ field }) => (
                      <Select
                        onValueChange={field.onChange}
                        defaultValue={field.value}
                        disabled={isSubmitting}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {CURRENCIES.map((currency) => (
                            <SelectItem key={currency.value} value={currency.value}>
                              {currency.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                </div>
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
                Create Deal
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

