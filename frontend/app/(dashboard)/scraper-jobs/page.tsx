"use client";

import { useState } from "react";
import { Plus, Database, Download, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
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
import { toast } from "sonner";

export default function ScraperJobsPage() {
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [jobType, setJobType] = useState("single");

  // Mock data - in real app, fetch from API
  const jobs = [
    {
      id: 1,
      type: "CIN Lookup",
      status: "completed",
      progress: 100,
      results: 1,
      created_at: "2024-01-15T10:30:00Z",
    },
    {
      id: 2,
      type: "Bulk Scrape",
      status: "running",
      progress: 65,
      results: 13,
      created_at: "2024-01-15T09:15:00Z",
    },
    {
      id: 3,
      type: "CIN Lookup",
      status: "failed",
      progress: 0,
      results: 0,
      created_at: "2024-01-14T16:45:00Z",
    },
  ];

  const getStatusBadge = (status: string) => {
    const statusConfig: Record<string, { label: string; className: string }> = {
      pending: { label: "Pending", className: "bg-gray-100 text-gray-800" },
      running: { label: "Running", className: "bg-blue-100 text-blue-800" },
      completed: { label: "Completed", className: "bg-green-100 text-green-800" },
      failed: { label: "Failed", className: "bg-red-100 text-red-800" },
    };

    const config = statusConfig[status] || statusConfig.pending;
    return (
      <Badge variant="outline" className={config.className}>
        {config.label}
      </Badge>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Scraper Jobs</h1>
          <p className="text-muted-foreground">
            Scrape company credit rating data from Infomerics
          </p>
        </div>
        <Button onClick={() => setShowCreateDialog(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Scraper Job
        </Button>
      </div>

      {/* Jobs List */}
      {jobs.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <Database className="h-16 w-16 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No scraper jobs yet</h3>
            <p className="text-muted-foreground text-center mb-6 max-w-md">
              Create your first scraper job to fetch company credit ratings
            </p>
            <Button onClick={() => setShowCreateDialog(true)}>
              <Plus className="mr-2 h-4 w-4" />
              New Scraper Job
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {jobs.map((job) => (
            <Card key={job.id} className="hover:shadow-md transition-shadow">
              <CardContent className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1 space-y-4">
                    <div className="flex items-center gap-3">
                      <h3 className="text-lg font-semibold">{job.type}</h3>
                      {getStatusBadge(job.status)}
                    </div>

                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Status</p>
                        <p className="text-sm font-medium">{job.status}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Results</p>
                        <p className="text-sm font-medium">{job.results} companies</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Created</p>
                        <p className="text-sm font-medium">
                          {new Date(job.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>

                    {job.status === "running" && (
                      <div className="space-y-2">
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">Progress</span>
                          <span className="font-medium">{job.progress}%</span>
                        </div>
                        <Progress value={job.progress} className="h-2" />
                      </div>
                    )}
                  </div>

                  <div className="flex gap-2 ml-6">
                    {job.status === "completed" && (
                      <Button variant="outline" size="icon" title="Download Results">
                        <Download className="h-4 w-4" />
                      </Button>
                    )}
                    {job.status === "running" && (
                      <Button
                        variant="outline"
                        size="icon"
                        title="Cancel Job"
                        className="text-destructive hover:text-destructive"
                      >
                        <XCircle className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create Job Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Create Scraper Job</DialogTitle>
            <DialogDescription>
              Fetch company credit rating data from Infomerics
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="job_type">Job Type</Label>
              <Select value={jobType} onValueChange={setJobType}>
                <SelectTrigger>
                  <SelectValue placeholder="Select job type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="single">Single CIN Lookup</SelectItem>
                  <SelectItem value="bulk">Bulk CIN Scrape</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {jobType === "single" && (
              <div className="space-y-2">
                <Label htmlFor="cin">CIN (Corporate Identification Number)</Label>
                <Input
                  id="cin"
                  placeholder="L12345MH2020PTC123456"
                  maxLength={21}
                />
                <p className="text-xs text-muted-foreground">
                  Enter a single CIN to fetch company data
                </p>
              </div>
            )}

            {jobType === "bulk" && (
              <div className="space-y-2">
                <Label htmlFor="cins">CINs (one per line)</Label>
                <Textarea
                  id="cins"
                  placeholder="L12345MH2020PTC123456&#10;L98765DL2019PLC987654&#10;..."
                  rows={6}
                />
                <p className="text-xs text-muted-foreground">
                  Enter multiple CINs, one per line
                </p>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                toast.success("Scraper job created successfully");
                setShowCreateDialog(false);
              }}
            >
              Create Job
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

