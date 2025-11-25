"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import apiClient from "@/lib/api-client";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/data-table/data-table";
import { columns, type Company } from "./_components/columns";
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
import { companySchema, type CompanyFormData } from "@/lib/form-schemas";
import { Loader2 } from "lucide-react";

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const searchParams = useSearchParams();

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<CompanyFormData>({
    resolver: zodResolver(companySchema),
    defaultValues: {
      company_name: "",
      cin: "",
    },
  });

  useEffect(() => {
    fetchCompanies();
    
    // Check if action=add is in query params
    if (searchParams.get("action") === "add") {
      setShowAddDialog(true);
    }
  }, [searchParams]);

  const fetchCompanies = async () => {
    try {
      setIsLoading(true);
      const response = await apiClient.getCompanies({ limit: 1000 });
      setCompanies(response.data);
    } catch (error) {
      console.error("Error fetching companies:", error);
      toast.error("Failed to fetch companies");
    } finally {
      setIsLoading(false);
    }
  };

  const onSubmit = async (data: CompanyFormData) => {
    setIsSubmitting(true);
    try {
      await apiClient.createCompany({
        company_name: data.company_name,
        cin: data.cin || undefined,
      });
      toast.success("Company created successfully");
      setShowAddDialog(false);
      reset();
    fetchCompanies();
    } catch (error: any) {
      console.error("Error creating company:", error);
      toast.error(error.response?.data?.detail || "Failed to create company");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Companies</h1>
          <p className="text-muted-foreground">Manage your company records and relationships</p>
        </div>
        <Button onClick={() => setShowAddDialog(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Company
        </Button>
      </div>

      {/* Data Table */}
      <DataTable
        columns={columns}
        data={companies}
        searchKey="company_name"
        searchPlaceholder="Search companies..."
        isLoading={isLoading}
      />

      {/* Add Company Dialog */}
      <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add New Company</DialogTitle>
            <DialogDescription>
              Create a new company record in your CRM
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)}>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="company_name">Company Name *</Label>
                <Input
                  id="company_name"
                  placeholder="Acme Corporation"
                  {...register("company_name")}
                  disabled={isSubmitting}
                />
                {errors.company_name && (
                  <p className="text-sm text-destructive">{errors.company_name.message}</p>
                )}
          </div>
              <div className="space-y-2">
                <Label htmlFor="cin">CIN (Corporate Identification Number)</Label>
                <Input
                  id="cin"
                  placeholder="L12345MH2020PTC123456"
                  maxLength={21}
                  {...register("cin")}
                  disabled={isSubmitting}
                />
                {errors.cin && (
                  <p className="text-sm text-destructive">{errors.cin.message}</p>
                )}
                <p className="text-xs text-muted-foreground">
                  Optional. 21-character unique identifier for Indian companies
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
                Create Company
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
