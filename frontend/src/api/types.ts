import type { components } from "./schema";

type Schemas = components["schemas"];

export type Me = Schemas["MeResponse"];
export type AuthResponse = Schemas["AuthResponse"];
export type AuthWithRecoveryCode = Schemas["AuthWithRecoveryCodeResponse"];
export type SignupRequest = Schemas["SignupRequest"];
export type LoginRequest = Schemas["LoginRequest"];
export type RecoverRequest = Schemas["RecoverRequest"];
export type ChangePasswordRequest = Schemas["ChangePasswordRequest"];
export type RecoveryCodeResponse = Schemas["RecoveryCodeResponse"];
export type UsernameIdeas = Schemas["UsernameIdeasResponse"];
