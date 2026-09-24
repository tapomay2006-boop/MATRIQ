import { z } from "zod";

// ─────────────────────────────────────────────
// User Role Definition
// ─────────────────────────────────────────────
export const userRoleSchema = z.enum(["cpse_admin", "national_admin"], {
  errorMap: () => ({ message: "Please select an authorized role (CPSE Admin or National Admin)" }),
});

export type UserRole = z.infer<typeof userRoleSchema>;

export const ROLE_LABELS: Record<UserRole, { label: string; description: string; dashboard: string }> = {
  cpse_admin: {
    label: "CPSE Admin",
    description: "Enterprise catalog ingestion, local duplicate resolution & harmonization",
    dashboard: "/dashboard_cpse",
  },
  national_admin: {
    label: "National Admin",
    description: "National directory governance, cross-CPSE deduplication & review queue approval",
    dashboard: "/dashboard_national",
  },
};

// ─────────────────────────────────────────────
// Signup Schema
// ─────────────────────────────────────────────
export const signupSchema = z
  .object({
    name: z
      .string()
      .min(2, "Name must be at least 2 characters")
      .max(50, "Name must be under 50 characters")
      .trim(),

    email: z
      .string()
      .email("Please enter a valid email address")
      .toLowerCase()
      .trim(),

    role: userRoleSchema,

    password: z
      .string()
      .min(8, "Password must be at least 8 characters")
      .regex(/[A-Z]/, "Password must contain at least one uppercase letter")
      .regex(/[a-z]/, "Password must contain at least one lowercase letter")
      .regex(/[0-9]/, "Password must contain at least one number")
      .regex(
        /[^A-Za-z0-9]/,
        "Password must contain at least one special character"
      ),

    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

// ─────────────────────────────────────────────
// Login Schema
// ─────────────────────────────────────────────
export const loginSchema = z.object({
  email: z
    .string()
    .email("Please enter a valid email address")
    .toLowerCase()
    .trim(),

  password: z.string().min(1, "Password is required"),
});

// ─────────────────────────────────────────────
// Inferred TypeScript types
// ─────────────────────────────────────────────
export type SignupInput = z.infer<typeof signupSchema>;
export type LoginInput = z.infer<typeof loginSchema>;
