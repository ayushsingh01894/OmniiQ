import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";

import { TextField } from "../../components/forms/TextField";
import { Button } from "../../components/ui/Button";
import { ApiError } from "../../lib/api";
import { AuthLayout } from "./AuthLayout";
import { useAuth } from "./AuthProvider";

const schema = z.object({
  email: z.email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});
type Values = z.infer<typeof schema>;

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "invalid_credentials") return "Email or password is incorrect.";
    if (error.status === 429) return "Too many attempts. Wait a minute and try again.";
  }
  return "Couldn't sign in. Check your connection and try again.";
}

export function LoginPage() {
  const { login } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(async ({ email, password }) => {
    setFormError(null);
    try {
      await login(email, password);
    } catch (error) {
      setFormError(messageFor(error));
    }
  });

  return (
    <AuthLayout title="Sign in">
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          error={errors.email?.message}
          {...register("email")}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          error={errors.password?.message}
          {...register("password")}
        />
        {formError ? (
          <p role="alert" className="text-sm text-danger">
            {formError}
          </p>
        ) : null}
        <Button type="submit" disabled={isSubmitting} className="w-full">
          {isSubmitting ? "Signing in…" : "Sign in"}
        </Button>
      </form>
      <p className="mt-4 text-sm text-muted">
        New here?{" "}
        <Link to="/register" className="font-medium text-accent underline underline-offset-2">
          Create an account
        </Link>
      </p>
    </AuthLayout>
  );
}
