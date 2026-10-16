import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { login as loginRequest, signup as signupRequest } from "../api";
import { useAuth } from "../auth/AuthContext";
import PasswordField from "../components/PasswordField";
import { isPasswordValid, PASSWORD_RULES_NOTE } from "../password";

export default function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const isSignup = mode === "signup";
  const { login } = useAuth();
  const navigate = useNavigate();

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [confirmVisible, setConfirmVisible] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (isSignup) {
      if (!isPasswordValid(password)) {
        setError(PASSWORD_RULES_NOTE);
        return;
      }
      if (password !== confirmPassword) {
        setError("Passwords do not match.");
        return;
      }
    }

    setSubmitting(true);
    try {
      const user = isSignup
        ? await signupRequest({
            first_name: firstName,
            last_name: lastName,
            email,
            password,
            confirm_password: confirmPassword,
          })
        : await loginRequest({ email, password });
      login(user);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="prose">
      <h1>{isSignup ? "Create Account" : "Log In"}</h1>
      <form className="auth-form" onSubmit={onSubmit}>
        {isSignup && (
          <>
            <label>
              First name
              <input
                name="first_name"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                autoComplete="given-name"
                required
              />
            </label>
            <label>
              Last name
              <input
                name="last_name"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                autoComplete="family-name"
                required
              />
            </label>
          </>
        )}
        <label>
          Email
          <input
            name="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </label>
        <PasswordField
          label="Password"
          name="password"
          value={password}
          onChange={setPassword}
          visible={passwordVisible}
          onToggleVisible={() => setPasswordVisible((v) => !v)}
          autoComplete={isSignup ? "new-password" : "current-password"}
        />
        {isSignup && (
          <>
            <p className="note">{PASSWORD_RULES_NOTE}</p>
            <PasswordField
              label="Confirm password"
              name="confirm_password"
              value={confirmPassword}
              onChange={setConfirmPassword}
              visible={confirmVisible}
              onToggleVisible={() => setConfirmVisible((v) => !v)}
              autoComplete="new-password"
            />
          </>
        )}
        {error && <p className="error">{error}</p>}
        <button className="btn" type="submit" disabled={submitting}>
          {submitting ? "Please wait…" : isSignup ? "Create Account" : "Log In"}
        </button>
      </form>
    </section>
  );
}
