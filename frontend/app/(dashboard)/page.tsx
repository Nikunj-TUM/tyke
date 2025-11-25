"use client";

import { useEffect, useState } from "react";
import apiClient from "@/lib/api-client";
import { Building2, Users, TrendingUp, MessageSquare, Megaphone, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import Link from "next/link";
import { AreaChart } from "@/components/charts/area-chart";
import { BarChart } from "@/components/charts/bar-chart";
import { CHART_COLORS } from "@/lib/constants";
import { motion } from "framer-motion";

interface Stats {
  companies_count: number;
  contacts_count: number;
  deals_count: number;
  active_campaigns_count: number;
  whatsapp_instances_count: number;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await apiClient.getOrganizationStats();
      setStats(response.data);
    } catch (error) {
      console.error("Error fetching stats:", error);
    } finally {
      setIsLoading(false);
    }
  };

  // Mock chart data (in real app, fetch from API)
  const companiesGrowthData = [
    { month: "Jan", count: 40 },
    { month: "Feb", count: 52 },
    { month: "Mar", count: 68 },
    { month: "Apr", count: 75 },
    { month: "May", count: 88 },
    { month: "Jun", count: 95 },
  ];

  const campaignPerformanceData = [
    { campaign: "Q1 Outreach", sent: 450, delivered: 432 },
    { campaign: "Q2 Promo", sent: 680, delivered: 658 },
    { campaign: "Summer Sale", sent: 320, delivered: 305 },
    { campaign: "Product Launch", sent: 520, delivered: 498 },
  ];

  const statCards = [
    {
      name: "Companies",
      value: stats?.companies_count || 0,
      icon: Building2,
      trend: "+12.5%",
      trendUp: true,
      color: "text-blue-600",
      bgColor: "bg-blue-100 dark:bg-blue-950",
      href: "/companies",
    },
    {
      name: "Contacts",
      value: stats?.contacts_count || 0,
      icon: Users,
      trend: "+8.3%",
      trendUp: true,
      color: "text-green-600",
      bgColor: "bg-green-100 dark:bg-green-950",
      href: "/contacts",
    },
    {
      name: "Active Deals",
      value: stats?.deals_count || 0,
      icon: TrendingUp,
      trend: "+24.1%",
      trendUp: true,
      color: "text-purple-600",
      bgColor: "bg-purple-100 dark:bg-purple-950",
      href: "/deals",
    },
    {
      name: "Active Campaigns",
      value: stats?.active_campaigns_count || 0,
      icon: Megaphone,
      trend: "-2.4%",
      trendUp: false,
      color: "text-orange-600",
      bgColor: "bg-orange-100 dark:bg-orange-950",
      href: "/campaigns",
    },
    {
      name: "WhatsApp Instances",
      value: stats?.whatsapp_instances_count || 0,
      icon: MessageSquare,
      trend: "+5.0%",
      trendUp: true,
      color: "text-emerald-600",
      bgColor: "bg-emerald-100 dark:bg-emerald-950",
      href: "/whatsapp",
    },
  ];

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <Skeleton className="h-8 w-[200px]" />
          <Skeleton className="h-4 w-[300px] mt-2" />
        </div>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">Welcome back! Here's your CRM overview</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {statCards.map((card, index) => (
          <motion.div
            key={card.name}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: index * 0.1 }}
          >
            <Link href={card.href}>
              <Card className="hover:shadow-lg transition-shadow cursor-pointer">
                <CardContent className="p-6">
            <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <p className="text-sm font-medium text-muted-foreground">{card.name}</p>
                      <p className="mt-2 text-3xl font-bold">{card.value.toLocaleString()}</p>
                      <div className="mt-2 flex items-center gap-1 text-xs">
                        {card.trendUp ? (
                          <ArrowUpRight className="h-3 w-3 text-green-600" />
                        ) : (
                          <ArrowDownRight className="h-3 w-3 text-red-600" />
                        )}
                        <span className={card.trendUp ? "text-green-600" : "text-red-600"}>
                          {card.trend}
                        </span>
                        <span className="text-muted-foreground">from last month</span>
                      </div>
              </div>
              <div className={`p-3 rounded-full ${card.bgColor}`}>
                <card.icon className={`h-6 w-6 ${card.color}`} />
              </div>
            </div>
                </CardContent>
              </Card>
            </Link>
          </motion.div>
        ))}
      </div>

      {/* Charts Section */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-7">
        <Card className="col-span-4">
          <CardHeader>
            <CardTitle>Company Growth</CardTitle>
            <CardDescription>Number of companies over the last 6 months</CardDescription>
          </CardHeader>
          <CardContent>
            <AreaChart
              data={companiesGrowthData}
              dataKey="count"
              xAxisKey="month"
              color={CHART_COLORS.primary}
            />
          </CardContent>
        </Card>

        <Card className="col-span-3">
          <CardHeader>
            <CardTitle>Campaign Performance</CardTitle>
            <CardDescription>Messages sent vs delivered</CardDescription>
          </CardHeader>
          <CardContent>
            <BarChart
              data={campaignPerformanceData}
              dataKey="sent"
              xAxisKey="campaign"
              color={CHART_COLORS.success}
            />
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions & Recent Activities */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>Common tasks to get you started</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button variant="outline" className="w-full justify-start" asChild>
              <Link href="/companies?action=add">
                <Building2 className="mr-2 h-4 w-4" />
              Add New Company
              </Link>
            </Button>
            <Button variant="outline" className="w-full justify-start" asChild>
              <Link href="/contacts?action=add">
                <Users className="mr-2 h-4 w-4" />
              Add New Contact
              </Link>
            </Button>
            <Button variant="outline" className="w-full justify-start" asChild>
              <Link href="/deals?action=add">
                <TrendingUp className="mr-2 h-4 w-4" />
                Create New Deal
              </Link>
            </Button>
            <Button variant="outline" className="w-full justify-start" asChild>
              <Link href="/campaigns?action=create">
                <Megaphone className="mr-2 h-4 w-4" />
              Create Campaign
              </Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Getting Started</CardTitle>
            <CardDescription>Set up your CRM in a few simple steps</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
            <div className="flex items-start gap-3">
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">
                1
              </div>
                <div className="flex-1">
                  <p className="font-medium text-sm">Add WhatsApp Instance</p>
                  <p className="text-sm text-muted-foreground">Connect your WhatsApp number to start messaging</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">
                2
              </div>
                <div className="flex-1">
                  <p className="font-medium text-sm">Import Contacts</p>
                  <p className="text-sm text-muted-foreground">Add your company contacts to the CRM</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">
                3
              </div>
                <div className="flex-1">
                  <p className="font-medium text-sm">Create Campaign</p>
                  <p className="text-sm text-muted-foreground">Start your first WhatsApp outreach campaign</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
