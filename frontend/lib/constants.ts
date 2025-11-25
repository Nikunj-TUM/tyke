// Deal stages
export const DEAL_STAGES = [
  { value: "lead", label: "Lead", color: "bg-gray-100 text-gray-800" },
  { value: "qualified", label: "Qualified", color: "bg-blue-100 text-blue-800" },
  { value: "proposal", label: "Proposal", color: "bg-purple-100 text-purple-800" },
  { value: "negotiation", label: "Negotiation", color: "bg-orange-100 text-orange-800" },
  { value: "closed_won", label: "Closed Won", color: "bg-green-100 text-green-800" },
  { value: "closed_lost", label: "Closed Lost", color: "bg-red-100 text-red-800" },
] as const;

// Campaign statuses
export const CAMPAIGN_STATUSES = [
  { value: "draft", label: "Draft", color: "bg-gray-100 text-gray-800" },
  { value: "scheduled", label: "Scheduled", color: "bg-blue-100 text-blue-800" },
  { value: "running", label: "Running", color: "bg-green-100 text-green-800" },
  { value: "paused", label: "Paused", color: "bg-yellow-100 text-yellow-800" },
  { value: "completed", label: "Completed", color: "bg-purple-100 text-purple-800" },
  { value: "failed", label: "Failed", color: "bg-red-100 text-red-800" },
] as const;

// User roles
export const USER_ROLES = [
  { value: "owner", label: "Owner", description: "Full access to all features" },
  { value: "admin", label: "Admin", description: "Manage team and most features" },
  { value: "member", label: "Member", description: "Limited access to features" },
] as const;

// Currency options
export const CURRENCIES = [
  { value: "INR", label: "₹ INR - Indian Rupee", symbol: "₹" },
  { value: "USD", label: "$ USD - US Dollar", symbol: "$" },
  { value: "EUR", label: "€ EUR - Euro", symbol: "€" },
  { value: "GBP", label: "£ GBP - British Pound", symbol: "£" },
] as const;

// Timezone options (common ones)
export const TIMEZONES = [
  { value: "Asia/Kolkata", label: "(GMT+5:30) India Standard Time" },
  { value: "America/New_York", label: "(GMT-5:00) Eastern Time" },
  { value: "America/Los_Angeles", label: "(GMT-8:00) Pacific Time" },
  { value: "Europe/London", label: "(GMT+0:00) London" },
  { value: "Asia/Dubai", label: "(GMT+4:00) Dubai" },
  { value: "Asia/Singapore", label: "(GMT+8:00) Singapore" },
] as const;

// Date format options
export const DATE_FORMATS = [
  { value: "DD/MM/YYYY", label: "DD/MM/YYYY (31/12/2024)" },
  { value: "MM/DD/YYYY", label: "MM/DD/YYYY (12/31/2024)" },
  { value: "YYYY-MM-DD", label: "YYYY-MM-DD (2024-12-31)" },
  { value: "DD MMM YYYY", label: "DD MMM YYYY (31 Dec 2024)" },
] as const;

// Company size options
export const COMPANY_SIZES = [
  { value: "1-10", label: "1-10 employees" },
  { value: "11-50", label: "11-50 employees" },
  { value: "51-200", label: "51-200 employees" },
  { value: "201-500", label: "201-500 employees" },
  { value: "501-1000", label: "501-1000 employees" },
  { value: "1001+", label: "1001+ employees" },
] as const;

// Industry options
export const INDUSTRIES = [
  { value: "technology", label: "Technology" },
  { value: "finance", label: "Finance & Banking" },
  { value: "healthcare", label: "Healthcare" },
  { value: "education", label: "Education" },
  { value: "manufacturing", label: "Manufacturing" },
  { value: "retail", label: "Retail & E-commerce" },
  { value: "real_estate", label: "Real Estate" },
  { value: "consulting", label: "Consulting" },
  { value: "other", label: "Other" },
] as const;

// Tag colors
export const TAG_COLORS = [
  "bg-blue-100 text-blue-800",
  "bg-green-100 text-green-800",
  "bg-purple-100 text-purple-800",
  "bg-orange-100 text-orange-800",
  "bg-pink-100 text-pink-800",
  "bg-indigo-100 text-indigo-800",
  "bg-red-100 text-red-800",
  "bg-yellow-100 text-yellow-800",
] as const;

// Pagination options
export const PAGE_SIZE_OPTIONS = [10, 25, 50, 100] as const;

// Default page size
export const DEFAULT_PAGE_SIZE = 25;

// Chart colors
export const CHART_COLORS = {
  primary: "hsl(var(--primary))",
  success: "hsl(var(--success))",
  warning: "hsl(var(--warning))",
  danger: "hsl(var(--destructive))",
  info: "hsl(var(--info))",
  muted: "hsl(var(--muted))",
} as const;

// Activity types
export const ACTIVITY_TYPES = [
  { value: "note", label: "Note", icon: "FileText" },
  { value: "call", label: "Call", icon: "Phone" },
  { value: "email", label: "Email", icon: "Mail" },
  { value: "meeting", label: "Meeting", icon: "Calendar" },
  { value: "whatsapp", label: "WhatsApp", icon: "MessageSquare" },
  { value: "task", label: "Task", icon: "CheckSquare" },
] as const;

// Keyboard shortcuts
export const KEYBOARD_SHORTCUTS = [
  { key: "⌘K", description: "Open command palette" },
  { key: "⌘N", description: "Create new item" },
  { key: "⌘S", description: "Save changes" },
  { key: "⌘F", description: "Search" },
  { key: "Esc", description: "Close dialog" },
] as const;

