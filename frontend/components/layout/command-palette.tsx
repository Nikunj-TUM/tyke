"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  Building2,
  Users,
  TrendingUp,
  MessageSquare,
  Megaphone,
  Database,
  Settings,
  Home,
  Plus,
  Search,
} from "lucide-react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const router = useRouter();

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        onOpenChange(!open);
      }
    };

    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, [open, onOpenChange]);

  const runCommand = React.useCallback(
    (command: () => void) => {
      onOpenChange(false);
      command();
    },
    [onOpenChange]
  );

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Type a command or search..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        
        <CommandGroup heading="Navigation">
          <CommandItem
            onSelect={() => runCommand(() => router.push("/"))}
          >
            <Home className="mr-2 h-4 w-4" />
            <span>Dashboard</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/companies"))}
          >
            <Building2 className="mr-2 h-4 w-4" />
            <span>Companies</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/contacts"))}
          >
            <Users className="mr-2 h-4 w-4" />
            <span>Contacts</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/deals"))}
          >
            <TrendingUp className="mr-2 h-4 w-4" />
            <span>Deals</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/whatsapp"))}
          >
            <MessageSquare className="mr-2 h-4 w-4" />
            <span>WhatsApp</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/campaigns"))}
          >
            <Megaphone className="mr-2 h-4 w-4" />
            <span>Campaigns</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/scraper-jobs"))}
          >
            <Database className="mr-2 h-4 w-4" />
            <span>Scraper Jobs</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/settings"))}
          >
            <Settings className="mr-2 h-4 w-4" />
            <span>Settings</span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Quick Actions">
          <CommandItem
            onSelect={() => runCommand(() => {
              // This would open a "add company" dialog
              router.push("/companies?action=add");
            })}
          >
            <Plus className="mr-2 h-4 w-4" />
            <span>Add Company</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => {
              router.push("/contacts?action=add");
            })}
          >
            <Plus className="mr-2 h-4 w-4" />
            <span>Add Contact</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => {
              router.push("/deals?action=add");
            })}
          >
            <Plus className="mr-2 h-4 w-4" />
            <span>Create Deal</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => {
              router.push("/campaigns?action=create");
            })}
          >
            <Plus className="mr-2 h-4 w-4" />
            <span>Create Campaign</span>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}

