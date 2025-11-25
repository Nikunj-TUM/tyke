"use client";

import { ColumnDef } from "@tanstack/react-table";
import { Building2, MoreHorizontal, ExternalLink, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
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

export interface Company {
  id: number;
  company_name: string;
  cin: string | null;
  rating_count: number;
  contact_count: number;
  deal_count: number;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export const columns: ColumnDef<Company>[] = [
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
    accessorKey: "company_name",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Company" />
    ),
    cell: ({ row }) => (
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
          <Building2 className="h-5 w-5 text-primary" />
        </div>
        <div className="min-w-0">
          <Link
            href={`/companies/${row.original.id}`}
            className="font-medium hover:underline block truncate"
          >
            {row.original.company_name}
          </Link>
          {row.original.cin && (
            <div className="text-xs text-muted-foreground truncate">{row.original.cin}</div>
          )}
        </div>
      </div>
    ),
  },
  {
    accessorKey: "rating_count",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Ratings" />
    ),
    cell: ({ row }) => (
      <Badge variant="secondary" className="font-mono">
        {row.original.rating_count}
      </Badge>
    ),
  },
  {
    accessorKey: "contact_count",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Contacts" />
    ),
    cell: ({ row }) => (
      <Badge variant="outline" className="font-mono">
        {row.original.contact_count}
      </Badge>
    ),
  },
  {
    accessorKey: "deal_count",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Deals" />
    ),
    cell: ({ row }) => (
      <Badge variant="outline" className="font-mono">
        {row.original.deal_count}
      </Badge>
    ),
  },
  {
    accessorKey: "tags",
    header: "Tags",
    cell: ({ row }) => {
      const tags = row.original.tags || [];
      if (tags.length === 0) return <span className="text-muted-foreground text-sm">—</span>;
      
      return (
        <div className="flex gap-1 flex-wrap max-w-[200px]">
          {tags.slice(0, 2).map((tag) => (
            <Badge key={tag} variant="default" className="text-xs">
              {tag}
            </Badge>
          ))}
          {tags.length > 2 && (
            <Badge variant="outline" className="text-xs">
              +{tags.length - 2}
            </Badge>
          )}
        </div>
      );
    },
    enableSorting: false,
  },
  {
    id: "actions",
    cell: ({ row }) => {
      const company = row.original;

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
              <Link href={`/companies/${company.id}`}>
                <ExternalLink className="mr-2 h-4 w-4" />
                View Details
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem>
              <Pencil className="mr-2 h-4 w-4" />
              Edit
            </DropdownMenuItem>
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

