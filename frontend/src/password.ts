export const PASSWORD_RULES_NOTE =
  "Password must be at least 8 characters and include at least one uppercase letter, " +
  "one lowercase letter, one number, and one special character.";

const PASSWORD_PATTERN = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9])\S{8,}$/;

export function isPasswordValid(password: string): boolean {
  return PASSWORD_PATTERN.test(password);
}
