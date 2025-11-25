import { z } from "zod";

// Authentication schemas
export const loginSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(6, "Password must be at least 6 characters"),
  remember: z.boolean().optional(),
});

export const signupSchema = z.object({
  organization_name: z.string().min(2, "Organization name must be at least 2 characters"),
  email: z.string().email("Invalid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  confirm_password: z.string(),
  first_name: z.string().min(2, "First name must be at least 2 characters"),
  last_name: z.string().min(2, "Last name must be at least 2 characters"),
  terms: z.boolean().refine(val => val === true, "You must accept the terms and conditions"),
}).refine((data) => data.password === data.confirm_password, {
  message: "Passwords don't match",
  path: ["confirm_password"],
});

export const forgotPasswordSchema = z.object({
  email: z.string().email("Invalid email address"),
});

export const resetPasswordSchema = z.object({
  password: z.string().min(8, "Password must be at least 8 characters"),
  confirm_password: z.string(),
}).refine((data) => data.password === data.confirm_password, {
  message: "Passwords don't match",
  path: ["confirm_password"],
});

// Company schemas
export const companySchema = z.object({
  company_name: z.string().min(1, "Company name is required").max(500),
  cin: z.string().max(21).optional().or(z.literal("")),
  industry: z.string().optional(),
  company_size: z.string().optional(),
  website: z.string().url("Invalid URL").optional().or(z.literal("")),
  notes: z.string().optional(),
  tags: z.array(z.string()).optional(),
});

// Contact schemas
export const contactSchema = z.object({
  full_name: z.string().min(1, "Full name is required").max(255),
  mobile_number: z.string().max(50).optional().or(z.literal("")),
  email_address: z.string().email("Invalid email address").optional().or(z.literal("")),
  din: z.string().max(50).optional().or(z.literal("")),
  company_id: z.number().optional().nullable(),
  addresses: z.record(z.string(), z.any()).optional(),
  notes: z.string().optional(),
  tags: z.array(z.string()).optional(),
});

// Deal schemas
export const dealSchema = z.object({
  title: z.string().min(1, "Title is required").max(255),
  description: z.string().optional(),
  stage: z.enum(["lead", "qualified", "proposal", "negotiation", "closed_won", "closed_lost"]),
  value: z.number().min(0).optional().nullable(),
  currency: z.string().optional().default("INR"),
  probability: z.number().min(0).max(100).optional().default(0),
  company_id: z.number().optional().nullable(),
  contact_id: z.number().optional().nullable(),
  expected_close_date: z.string().optional().nullable(),
  notes: z.string().optional(),
});

// Campaign schemas
export const campaignSchema = z.object({
  name: z.string().min(1, "Campaign name is required").max(255),
  description: z.string().optional(),
  whatsapp_instance_id: z.number({
    message: "Please select a WhatsApp instance",
  }),
  message_template: z.string().min(1, "Message template is required"),
  schedule_type: z.enum(["immediate", "scheduled"]),
  scheduled_at: z.string().optional().nullable(),
  contact_ids: z.array(z.number()).min(1, "Please select at least one contact"),
});

// WhatsApp instance schemas
export const whatsappInstanceSchema = z.object({
  name: z.string().min(1, "Instance name is required").max(255),
  phone_number: z.string().min(10, "Invalid phone number").max(20),
  daily_message_limit: z.number().min(1).max(10000).optional().default(1000),
});

// Message template schemas
export const messageTemplateSchema = z.object({
  name: z.string().min(1, "Template name is required").max(255),
  content: z.string().min(1, "Template content is required"),
  variables: z.array(z.string()).optional(),
});

// User invite schemas
export const inviteUserSchema = z.object({
  email: z.string().email("Invalid email address"),
  first_name: z.string().min(2, "First name must be at least 2 characters"),
  last_name: z.string().min(2, "Last name must be at least 2 characters"),
  role: z.enum(["owner", "admin", "member"]),
});

// Settings schemas
export const organizationSettingsSchema = z.object({
  organization_name: z.string().min(2, "Organization name must be at least 2 characters"),
  industry: z.string().optional(),
  company_size: z.string().optional(),
  website: z.string().url("Invalid URL").optional().or(z.literal("")),
  timezone: z.string().optional(),
  currency: z.string().optional(),
  date_format: z.string().optional(),
});

export const userProfileSchema = z.object({
  first_name: z.string().min(2, "First name must be at least 2 characters"),
  last_name: z.string().min(2, "Last name must be at least 2 characters"),
  phone_number: z.string().optional().or(z.literal("")),
});

export const changePasswordSchema = z.object({
  current_password: z.string().min(1, "Current password is required"),
  new_password: z.string().min(8, "Password must be at least 8 characters"),
  confirm_password: z.string(),
}).refine((data) => data.new_password === data.confirm_password, {
  message: "Passwords don't match",
  path: ["confirm_password"],
});

// Export types
export type LoginFormData = z.infer<typeof loginSchema>;
export type SignupFormData = z.infer<typeof signupSchema>;
export type ForgotPasswordFormData = z.infer<typeof forgotPasswordSchema>;
export type ResetPasswordFormData = z.infer<typeof resetPasswordSchema>;
export type CompanyFormData = z.infer<typeof companySchema>;
export type ContactFormData = z.infer<typeof contactSchema>;
export type DealFormData = z.infer<typeof dealSchema>;
export type CampaignFormData = z.infer<typeof campaignSchema>;
export type WhatsAppInstanceFormData = z.infer<typeof whatsappInstanceSchema>;
export type MessageTemplateFormData = z.infer<typeof messageTemplateSchema>;
export type InviteUserFormData = z.infer<typeof inviteUserSchema>;
export type OrganizationSettingsFormData = z.infer<typeof organizationSettingsSchema>;
export type UserProfileFormData = z.infer<typeof userProfileSchema>;
export type ChangePasswordFormData = z.infer<typeof changePasswordSchema>;

