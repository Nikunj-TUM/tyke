"use client";

import { useAuth } from "@/lib/auth";
import { LogOut, User, Bell, Search, Moon, Sun, Command } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { useTheme } from "next-themes";
import { useState } from "react";
import { CommandPalette } from "./command-palette";

export default function Header() {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const [showCommandPalette, setShowCommandPalette] = useState(false);

  // Get user initials
  const initials = user?.first_name && user?.last_name
    ? `${user.first_name[0]}${user.last_name[0]}`.toUpperCase()
    : user?.email?.[0].toUpperCase() || "U";

  return (
    <>
      <header className="h-16 border-b bg-card px-6 flex items-center justify-between">
      <div className="flex items-center gap-4">
          <Button
            variant="outline"
            size="sm"
            className="gap-2"
            onClick={() => setShowCommandPalette(true)}
          >
            <Search className="h-4 w-4" />
            <span className="hidden md:inline">Search...</span>
            <kbd className="hidden md:inline pointer-events-none h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium opacity-100">
              <span className="text-xs">⌘</span>K
            </kbd>
          </Button>
        </div>
        
        <div className="flex items-center gap-2">
          {/* Theme Toggle */}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            <Sun className="h-5 w-5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
            <Moon className="absolute h-5 w-5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
            <span className="sr-only">Toggle theme</span>
          </Button>

          {/* Notifications */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="relative">
                <Bell className="h-5 w-5" />
                <Badge
                  variant="destructive"
                  className="absolute -top-1 -right-1 h-5 w-5 rounded-full p-0 flex items-center justify-center text-[10px]"
                >
                  3
                </Badge>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-80">
              <DropdownMenuLabel>Notifications</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <div className="max-h-96 overflow-y-auto">
                <div className="px-2 py-3 text-sm">
                  <p className="font-medium">New campaign completed</p>
                  <p className="text-muted-foreground text-xs mt-1">
                    Your campaign "Q4 Outreach" has been completed successfully.
                  </p>
                  <p className="text-muted-foreground text-xs mt-1">2 hours ago</p>
                </div>
                <DropdownMenuSeparator />
                <div className="px-2 py-3 text-sm">
                  <p className="font-medium">New contact added</p>
                  <p className="text-muted-foreground text-xs mt-1">
                    John Doe has been added to your contacts.
                  </p>
                  <p className="text-muted-foreground text-xs mt-1">5 hours ago</p>
                </div>
                <DropdownMenuSeparator />
                <div className="px-2 py-3 text-sm">
                  <p className="font-medium">Deal stage updated</p>
                  <p className="text-muted-foreground text-xs mt-1">
                    Deal "Enterprise Plan" moved to Negotiation stage.
                  </p>
                  <p className="text-muted-foreground text-xs mt-1">1 day ago</p>
                </div>
              </div>
              <DropdownMenuSeparator />
              <div className="p-2">
                <Button variant="ghost" size="sm" className="w-full">
                  View all notifications
                </Button>
              </div>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Organization Badge */}
          <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-md bg-muted">
            <Building2 className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">{user?.organization_name}</span>
          </div>

          {/* User Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="gap-2 pl-2">
                <Avatar className="h-8 w-8">
                  <AvatarFallback>{initials}</AvatarFallback>
                </Avatar>
                <div className="hidden md:flex flex-col items-start">
                  <span className="text-sm font-medium">
                    {user?.first_name} {user?.last_name}
                  </span>
                  <span className="text-xs text-muted-foreground capitalize">
                    {user?.role}
                  </span>
                </div>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel>
                <div className="flex flex-col space-y-1">
                  <p className="text-sm font-medium leading-none">
                    {user?.first_name} {user?.last_name}
                  </p>
                  <p className="text-xs leading-none text-muted-foreground">
                    {user?.email}
                  </p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <a href="/settings" className="cursor-pointer">
                  <User className="mr-2 h-4 w-4" />
                  Profile Settings
                </a>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={logout} className="text-destructive cursor-pointer">
                <LogOut className="mr-2 h-4 w-4" />
          Logout
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
      </div>
    </header>

      <CommandPalette open={showCommandPalette} onOpenChange={setShowCommandPalette} />
    </>
  );
}

// Add Building2 import
import { Building2 } from "lucide-react";
