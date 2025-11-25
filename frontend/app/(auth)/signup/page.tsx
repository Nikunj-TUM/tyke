"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { signupSchema, type SignupFormData } from "@/lib/form-schemas";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import { Building2, Loader2, ArrowRight, ArrowLeft, Check } from "lucide-react";
import { toast } from "sonner";
import { Progress } from "@/components/ui/progress";

export default function SignupPage() {
  const { signup } = useAuth();
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [step, setStep] = useState(1);

  const {
    register,
    handleSubmit,
    formState: { errors },
    watch,
    setValue,
    trigger,
  } = useForm<SignupFormData>({
    resolver: zodResolver(signupSchema),
    defaultValues: {
      organization_name: "",
      email: "",
      password: "",
      confirm_password: "",
      first_name: "",
      last_name: "",
      terms: false,
    },
  });

  const totalSteps = 3;
  const progress = (step / totalSteps) * 100;

  const onSubmit = async (data: SignupFormData) => {
    setError("");
    setIsLoading(true);

    try {
      await signup(data);
      toast.success("Account created!", {
        description: "Welcome to CRM Platform. Let's get started!",
      });
    } catch (err: any) {
      const errorMessage = err.message || "Signup failed. Please try again.";
      setError(errorMessage);
      toast.error("Signup failed", {
        description: errorMessage,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const nextStep = async () => {
    let fieldsToValidate: (keyof SignupFormData)[] = [];
    
    if (step === 1) {
      fieldsToValidate = ["organization_name"];
    } else if (step === 2) {
      fieldsToValidate = ["first_name", "last_name", "email"];
    }

    const isValid = await trigger(fieldsToValidate);
    if (isValid && step < totalSteps) {
      setStep(step + 1);
    }
  };

  const prevStep = () => {
    if (step > 1) {
      setStep(step - 1);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary/10 via-background to-secondary/10 p-4">
      <div className="w-full max-w-md">
        {/* Logo/Brand */}
        <div className="flex flex-col items-center mb-8">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg mb-4">
            <Building2 className="h-8 w-8" />
          </div>
          <h1 className="text-2xl font-bold">CRM Platform</h1>
          <p className="text-muted-foreground text-sm">Create your organization</p>
        </div>
        
        <Card className="shadow-xl">
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl font-bold">Sign up</CardTitle>
            <CardDescription>
              Step {step} of {totalSteps}
            </CardDescription>
            <Progress value={progress} className="mt-2" />
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
          )}
          
              {/* Step 1: Organization Details */}
              {step === 1 && (
                <div className="space-y-4 animate-fade-in">
                  <div className="space-y-2">
                    <Label htmlFor="organization_name">Organization Name</Label>
                    <Input
                id="organization_name"
                type="text"
                      placeholder="Acme Corp"
                      {...register("organization_name")}
                      disabled={isLoading}
                    />
                    {errors.organization_name && (
                      <p className="text-sm text-destructive">{errors.organization_name.message}</p>
                    )}
                  </div>
            </div>
              )}
            
              {/* Step 2: Personal Details */}
              {step === 2 && (
                <div className="space-y-4 animate-fade-in">
            <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="first_name">First Name</Label>
                      <Input
                  id="first_name"
                  type="text"
                        placeholder="John"
                        {...register("first_name")}
                        disabled={isLoading}
                      />
                      {errors.first_name && (
                        <p className="text-sm text-destructive">{errors.first_name.message}</p>
                      )}
              </div>
                    <div className="space-y-2">
                      <Label htmlFor="last_name">Last Name</Label>
                      <Input
                  id="last_name"
                  type="text"
                        placeholder="Doe"
                        {...register("last_name")}
                        disabled={isLoading}
                      />
                      {errors.last_name && (
                        <p className="text-sm text-destructive">{errors.last_name.message}</p>
                      )}
              </div>
            </div>
            
                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <Input
                id="email"
                type="email"
                      placeholder="you@example.com"
                      {...register("email")}
                      disabled={isLoading}
                    />
                    {errors.email && (
                      <p className="text-sm text-destructive">{errors.email.message}</p>
                    )}
                  </div>
            </div>
              )}

              {/* Step 3: Password & Confirmation */}
              {step === 3 && (
                <div className="space-y-4 animate-fade-in">
                  <div className="space-y-2">
                    <Label htmlFor="password">Password</Label>
                    <Input
                id="password"
                type="password"
                      placeholder="••••••••"
                      {...register("password")}
                      disabled={isLoading}
                    />
                    {errors.password && (
                      <p className="text-sm text-destructive">{errors.password.message}</p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      Must be at least 8 characters long
              </p>
            </div>
            
                  <div className="space-y-2">
                    <Label htmlFor="confirm_password">Confirm Password</Label>
                    <Input
                id="confirm_password"
                type="password"
                      placeholder="••••••••"
                      {...register("confirm_password")}
                      disabled={isLoading}
                    />
                    {errors.confirm_password && (
                      <p className="text-sm text-destructive">{errors.confirm_password.message}</p>
                    )}
                  </div>

                  <div className="flex items-start space-x-2 pt-2">
                    <Checkbox
                      id="terms"
                      checked={watch("terms")}
                      onCheckedChange={(checked) => setValue("terms", checked as boolean)}
                      disabled={isLoading}
                    />
                    <Label
                      htmlFor="terms"
                      className="text-sm font-normal leading-relaxed cursor-pointer"
                    >
                      I agree to the{" "}
                      <a href="#" className="text-primary hover:underline">
                        Terms of Service
                      </a>{" "}
                      and{" "}
                      <a href="#" className="text-primary hover:underline">
                        Privacy Policy
                      </a>
                    </Label>
            </div>
                  {errors.terms && (
                    <p className="text-sm text-destructive">{errors.terms.message}</p>
                  )}
          </div>
              )}

              {/* Navigation Buttons */}
              <div className="flex gap-2 pt-4">
                {step > 1 && (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={prevStep}
                    disabled={isLoading}
                  >
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Back
                  </Button>
                )}
                
                {step < totalSteps ? (
                  <Button
                    type="button"
                    onClick={nextStep}
                    disabled={isLoading}
                    className="flex-1"
                  >
                    Next
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                ) : (
                  <Button
            type="submit"
            disabled={isLoading}
                    className="flex-1"
                  >
                    {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    {!isLoading && <Check className="mr-2 h-4 w-4" />}
                    Create Account
                  </Button>
                )}
              </div>
        </form>
          </CardContent>
          <CardFooter className="flex flex-col space-y-4">
            <div className="text-sm text-center text-muted-foreground">
              Already have an account?{" "}
              <Link href="/login" className="text-primary hover:underline font-medium">
                Sign in
              </Link>
            </div>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}
