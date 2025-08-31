// src/lib/api.ts
import axios from "axios";

const BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, "") || "http://127.0.0.1:8000";

export const api = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
});

// ---- Types ----
export type Scenario =
  | "Fermeture d'Agence" | "Currency Devaluation" | "Energy Crisis"
  | "Political Uncertainty" | "Digital Transformation" | "Tourism Recovery"
  | "Export Boom" | "Economic Recovery" | "Regional Instability" | "Baseline";

export type Intensity = "Faible" | "Moyenne" | "Forte";
export type Segment = "Tous les segments" | "Premium" | "SME" | "Mass Market";
export type Region =
  | "Tunis" | "Sfax" | "Sousse" | "Kairouan" | "Bizerte" | "Gabès" | "Ariana" | "La Marsa";

export type SimRequest = {
  scenario: Scenario;
  intensity: Intensity;
  segment: Segment;
  region: Region;
  duration_months: number;
};

// ---- Calls ----
export const schema = () => api.get("/schema");
export const segments = (n_clusters = 4) => api.post("/segments", { n_clusters });
export const simulate = (payload: SimRequest) => api.post("/simulate", payload);
export const compare = (scenarios: SimRequest[]) => api.post("/compare", { scenarios });
