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
  display_name: z.string().trim().min(1, "Enter your name.").max(100, "Use 100 characters or fewer."),
  email: z.email("Enter a valid email address."),
  password: z
    .string()
    .min(10, "Use at least 10 characters.")
    .max(128, "Use 128 characters or fewer."),
});
type Values = z.infer<typeof schema>;

export function RegisterPage() {
  const { register: signUp } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await signUp(values);
    } catch (error) {
      if (error instanceof ApiError && error.code === "email_already_registered") {
        setError("email", { message: "An account with this email already exists." });
      } else if (error instanceof ApiError && error.status === 429) {
        setFormError("Too many sign-up attempts. Try again later.");
      } else {
        setFormError("Couldn't create the account. Check your connection and try again.");
      }
    }
  });

  return (
    <AuthLayout title="Create your account">
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <TextField
          label="Name"
          autoComplete="name"
          error={errors.display_name?.message}
          {...register("display_name")}
        />
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
          autoComplete="new-password"
          hint="At least 10 characters."
          error={errors.password?.message}
          {...register("password")}
        />
        {formError ? (
          <p role="alert" className="text-sm text-danger">
            {formError}
          </p>
        ) : null}
        <Button type="submit" disabled={isSubmitting} className="w-full">
          {isSubmitting ? "Creating account…" : "Create account"}
        </Button>
      </form>
      <p className="mt-4 text-sm text-muted">
        Already have an account?{" "}
        <Link to="/login" className="font-medium text-accent underline underline-offset-2">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  );
}
