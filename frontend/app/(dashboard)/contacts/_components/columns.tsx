"use client";

import { ColumnDef } from "@tanstack/react-table";
import { User, MoreHorizontal, ExternalLink, Pencil, Trash2, Mail, Phone, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DataTableColumnHeader } from "@/components/data-table/data-table-column-header";
import Link from "next/link";

export interface Contact {
  id: number;
  full_name: string;
  mobile_number: string | null;
  email_address: string | null;
  company_id: number | null;
  company_name: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export const columns: ColumnDef<Contact>[] = [
  {
    id: "select",
    header: ({ table }) => (
      <Checkbox
        checked={table.getIsAllPageRowsSelected()}
        onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
        aria-label="Select all"
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onCheckedChange={(value) => row.toggleSelected(!!value)}
        aria-label="Select row"
      />
    ),
    enableSorting: false,
    enableHiding: false,
  },
  {
    accessorKey: "full_name",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Name" />
    ),
    cell: ({ row }) => {
      const name = row.original.full_name;
      const initials = name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2);

      return (
        <div className="flex items-center gap-3">
          <Avatar className="h-10 w-10">
            <AvatarFallback className="bg-primary/10 text-primary">
              {initials}
            </AvatarFallback>
          </Avatar>
          <div className="min-w-0">
            <Link
              href={`/contacts/${row.original.id}`}
              className="font-medium hover:underline block truncate"
            >
              {name}
            </Link>
            {row.original.tags.length > 0 && (
              <div className="flex gap-1 mt-1">
                {row.original.tags.slice(0, 2).map((tag) => (
                  <Badge key={tag} variant="secondary" className="text-xs">
                    {tag}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </div>
      );
    },
  },
  {
    accessorKey: "company_name",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Company" />
    ),
    cell: ({ row }) => {
      const companyName = row.original.company_name;
      const companyId = row.original.company_id;

      if (!companyName) {
        return <span className="text-muted-foreground text-sm">—</span>;
      }

      if (companyId) {
        return (
          <Link
            href={`/companies/${companyId}`}
            className="text-sm hover:underline"
          >
            {companyName}
          </Link>
        );
      }

      return <span className="text-sm">{companyName}</span>;
    },
  },
  {
    accessorKey: "email_address",
    header: "Contact Info",
    cell: ({ row }) => {
      const email = row.original.email_address;
      const phone = row.original.mobile_number;

      return (
        <div className="space-y-1">
          {email && (
            <div className="flex items-center gap-2 text-sm">
              <Mail className="h-3 w-3 text-muted-foreground" />
              <a href={`mailto:${email}`} className="hover:underline truncate">
                {email}
              </a>
            </div>
          )}
          {phone && (
            <div className="flex items-center gap-2 text-sm">
              <Phone className="h-3 w-3 text-muted-foreground" />
              <a href={`tel:${phone}`} className="hover:underline">
                {phone}
              </a>
            </div>
          )}
          {!email && !phone && (
            <span className="text-muted-foreground text-sm">—</span>
          )}
        </div>
      );
    },
    enableSorting: false,
  },
  {
    id: "actions",
    cell: ({ row }) => {
      const contact = row.original;

      return (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <MoreHorizontal className="h-4 w-4" />
              <span className="sr-only">Open menu</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Actions</DropdownMenuLabel>
            <DropdownMenuItem asChild>
              <Link href={`/contacts/${contact.id}`}>
                <ExternalLink className="mr-2 h-4 w-4" />
                View Details
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem>
              <Pencil className="mr-2 h-4 w-4" />
              Edit
            </DropdownMenuItem>
            {contact.mobile_number && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link href={`/whatsapp?contact_id=${contact.id}`}>
                    <MessageSquare className="mr-2 h-4 w-4" />
                    Send WhatsApp
                  </Link>
                </DropdownMenuItem>
              </>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem className="text-destructive">
              <Trash2 className="mr-2 h-4 w-4" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );
    },
  },
];

