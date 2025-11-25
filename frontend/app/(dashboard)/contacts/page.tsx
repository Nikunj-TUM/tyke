"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import apiClient from "@/lib/api-client";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/data-table/data-table";
import { columns, type Contact } from "./_components/columns";
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
import { contactSchema, type ContactFormData } from "@/lib/form-schemas";
import { Loader2 } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";

export default function ContactsPage() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const searchParams = useSearchParams();

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<ContactFormData>({
    resolver: zodResolver(contactSchema),
    defaultValues: {
      full_name: "",
      mobile_number: "",
      email_address: "",
      din: "",
    },
  });

  useEffect(() => {
    fetchContacts();
    
    if (searchParams.get("action") === "add") {
      setShowAddDialog(true);
    }
  }, [searchParams]);

  const fetchContacts = async () => {
    try {
      setIsLoading(true);
      const response = await apiClient.getContacts({ limit: 1000 });
      setContacts(response.data);
    } catch (error) {
      console.error("Error fetching contacts:", error);
      toast.error("Failed to fetch contacts");
    } finally {
      setIsLoading(false);
    }
  };

  const onSubmit = async (data: ContactFormData) => {
    setIsSubmitting(true);
    try {
      await apiClient.createContact({
        full_name: data.full_name,
        mobile_number: data.mobile_number || undefined,
        email_address: data.email_address || undefined,
        din: data.din || undefined,
      });
      toast.success("Contact created successfully");
      setShowAddDialog(false);
      reset();
    fetchContacts();
    } catch (error: any) {
      console.error("Error creating contact:", error);
      toast.error(error.response?.data?.detail || "Failed to create contact");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Contacts</h1>
          <p className="text-muted-foreground">Manage your contact database and relationships</p>
        </div>
        <Button onClick={() => setShowAddDialog(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Contact
        </Button>
      </div>

      {/* Data Table */}
      <DataTable
        columns={columns}
        data={contacts}
        searchKey="full_name"
        searchPlaceholder="Search contacts by name, email, or phone..."
        isLoading={isLoading}
      />

      {/* Add Contact Dialog */}
      <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Add New Contact</DialogTitle>
            <DialogDescription>
              Create a new contact record in your CRM
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)}>
            <div className="space-y-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2 space-y-2">
                  <Label htmlFor="full_name">Full Name *</Label>
                  <Input
                    id="full_name"
                    placeholder="John Doe"
                    {...register("full_name")}
                    disabled={isSubmitting}
                  />
                  {errors.full_name && (
                    <p className="text-sm text-destructive">{errors.full_name.message}</p>
                  )}
      </div>

                <div className="space-y-2">
                  <Label htmlFor="mobile_number">Mobile Number</Label>
                  <Input
                    id="mobile_number"
                    type="tel"
                    placeholder="+91 98765 43210"
                    {...register("mobile_number")}
                    disabled={isSubmitting}
                  />
                  {errors.mobile_number && (
                    <p className="text-sm text-destructive">{errors.mobile_number.message}</p>
                  )}
                        </div>

                <div className="space-y-2">
                  <Label htmlFor="email_address">Email Address</Label>
                  <Input
                    id="email_address"
                    type="email"
                    placeholder="john@example.com"
                    {...register("email_address")}
                    disabled={isSubmitting}
                  />
                  {errors.email_address && (
                    <p className="text-sm text-destructive">{errors.email_address.message}</p>
                      )}
                    </div>

                <div className="col-span-2 space-y-2">
                  <Label htmlFor="din">DIN (Director Identification Number)</Label>
                  <Input
                    id="din"
                    placeholder="12345678"
                    maxLength={50}
                    {...register("din")}
                    disabled={isSubmitting}
                  />
                  {errors.din && (
                    <p className="text-sm text-destructive">{errors.din.message}</p>
                  )}
                  <p className="text-xs text-muted-foreground">
                    Optional. Unique identifier for company directors
                  </p>
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
                Create Contact
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
