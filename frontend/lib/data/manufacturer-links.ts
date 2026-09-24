/**
 * Authoritative manufacturer and company domain registry.
 * Maps known industrial OEMs, CPSE entities, and equipment manufacturers
 * to their verified official corporate websites.
 *
 * Used for dynamic manufacturer navigation in NEMISYS material search.
 */

export const MANUFACTURER_LINKS: Record<string, string> = {
  // Industrial Belts, Bearings & Power Transmission
  "ESCO": "https://www.escocorp.com",
  "FENNER": "https://www.fenner.com",
  "FENNER INDIA": "https://www.fenner.com",
  "PIX": "https://www.pixtrans.com",
  "PIX TRANSMISSIONS": "https://www.pixtrans.com",
  "SKF": "https://www.skf.com",
  "FAG": "https://www.schaeffler.com",
  "SCHAEFFLER": "https://www.schaeffler.com",
  "TIMKEN": "https://www.timken.com",
  "GATES": "https://www.gates.com",

  // Valves, Pumps, Hydraulics & Seals
  "AUDCO": "https://www.flowserve.com",
  "FLOWSERVE": "https://www.flowserve.com",
  "HYDAC": "https://www.hydac.com",
  "FLEXITALLIC": "https://www.flexitallic.com",
  "UNBRAKO": "https://www.unbrako.com",
  "SULZER": "https://www.sulzer.com",
  "KIRLOSKAR": "https://www.kirloskargroup.com",
  "KIRLOSKAR BROTHERS": "https://www.kirloskarpumps.com",

  // Heavy Electrical, Turbines & Automation
  "BHEL": "https://www.bhel.com",
  "BHARAT HEAVY ELECTRICALS": "https://www.bhel.com",
  "L&T": "https://www.larsentoubro.com",
  "LARSEN & TOUBRO": "https://www.larsentoubro.com",
  "SIEMENS": "https://www.siemens.com",
  "ABB": "https://global.abb",
  "SCHNEIDER": "https://www.se.com",
  "SCHNEIDER ELECTRIC": "https://www.se.com",
  "CROMPTON": "https://www.cgglobal.com",
  "CG POWER": "https://www.cgglobal.com",
  "HAVELLS": "https://www.havells.com",
  "CUMMINS": "https://www.cummins.com",
  "BOSCH": "https://www.bosch.com",

  // Instrumentation & Process Control
  "ENDRESS+HAUSER": "https://www.endress.com",
  "ENDRESS & HAUSER": "https://www.endress.com",
  "EMERSON": "https://www.emerson.com",
  "YOKOGAWA": "https://www.yokogawa.com",
  "THERMAX": "https://www.thermaxglobal.com",

  // Mining, Steel & Heavy Machinery
  "TATA STEEL": "https://www.tatasteel.com",
  "TATA": "https://www.tatasteel.com",
  "SAIL": "https://www.sail.co.in",
  "CATERPILLAR": "https://www.caterpillar.com",
  "CAT": "https://www.caterpillar.com",
  "KOMATSU": "https://www.komatsu.com",
  "VOLVO": "https://www.volvoce.com",
  "SANDVIK": "https://www.sandvik.com",
  "JCB": "https://www.jcb.com",
  "BHARAT FORGE": "https://www.bharatforge.com",

  // Indian Public Sector Undertakings (CPSEs)
  "NTPC": "https://www.ntpc.co.in",
  "ONGC": "https://www.ongcindia.com",
  "IOCL": "https://www.iocl.com",
  "INDIAN OIL": "https://www.iocl.com",
  "GAIL": "https://www.gailonline.com",
  "COAL INDIA": "https://www.coalindia.in",
  "CIL": "https://www.coalindia.in",
  "CCL": "https://www.centralcoalfields.in",
  "BPCL": "https://www.bharatpetroleum.in",
  "HPCL": "https://www.hindustanpetroleum.com",
};

/**
 * Normalizes a manufacturer or company string for dictionary matching.
 */
export function normalizeManufacturerKey(name: string): string {
  return name
    .trim()
    .toUpperCase()
    .replace(/[.,\-_/]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export interface ManufacturerUrlResult {
  url: string;
  isOfficial: boolean;
  name: string;
  label: string;
}

/**
 * Resolves an official website for a manufacturer or company.
 * If the manufacturer is registered in MANUFACTURER_LINKS, returns the verified URL.
 * Otherwise, generates a scoped Google fallback query (`<manufacturer> official site`)
 * to ensure the action never dead-ends.
 */
export function getManufacturerUrl(
  rawName?: string | null
): ManufacturerUrlResult | null {
  if (!rawName) return null;

  const cleaned = rawName.trim();
  if (
    !cleaned ||
    cleaned.toUpperCase() === "NA" ||
    cleaned.toUpperCase() === "NULL" ||
    cleaned.toUpperCase() === "NONE" ||
    cleaned === "—" ||
    cleaned === "-"
  ) {
    return null;
  }

  // 1. Direct dictionary match
  const directKey = cleaned.toUpperCase();
  if (MANUFACTURER_LINKS[directKey]) {
    return {
      url: MANUFACTURER_LINKS[directKey],
      isOfficial: true,
      name: cleaned,
      label: "Manufacturer",
    };
  }

  // 2. Normalized key match (handles punctuation / multi-space variations)
  const normalizedKey = normalizeManufacturerKey(cleaned);
  if (MANUFACTURER_LINKS[normalizedKey]) {
    return {
      url: MANUFACTURER_LINKS[normalizedKey],
      isOfficial: true,
      name: cleaned,
      label: "Manufacturer",
    };
  }

  // 3. Prefix / Substring match (e.g., "FENNER INDIA LTD" -> matches "FENNER")
  for (const [key, url] of Object.entries(MANUFACTURER_LINKS)) {
    if (
      normalizedKey === key ||
      normalizedKey.startsWith(`${key} `) ||
      normalizedKey.endsWith(` ${key}`)
    ) {
      return {
        url,
        isOfficial: true,
        name: cleaned,
        label: "Manufacturer",
      };
    }
  }

  // 4. Fallback: Google search for official site
  const fallbackQuery = `${cleaned} official site`;
  const fallbackUrl = `https://www.google.com/search?q=${encodeURIComponent(
    fallbackQuery
  )}`;

  return {
    url: fallbackUrl,
    isOfficial: false,
    name: cleaned,
    label: "Manufacturer",
  };
}

export interface MaterialQuerySource {
  description?: string | null;
  make?: string | null;
  manufacturer?: string | null;
  company?: string | null;
  part_number?: string | null;
}

/**
 * Dynamically builds an optimized Google search query for a material.
 * Preferred order: description + manufacturer/make + part_number
 * Gracefully handles missing manufacturer, part number, or description.
 */
export function buildMaterialGoogleQuery(item: MaterialQuerySource): string {
  // Resolve most specific manufacturer/make: prefer make or manufacturer
  const mfg =
    item.make && item.make.trim().toUpperCase() !== "NA"
      ? item.make.trim()
      : item.manufacturer && item.manufacturer.trim().toUpperCase() !== "NA"
        ? item.manufacturer.trim()
        : "";

  const partNo =
    item.part_number && item.part_number.trim().toUpperCase() !== "NA"
      ? item.part_number.trim()
      : "";

  const desc =
    item.description && item.description.trim().toUpperCase() !== "NA"
      ? item.description.trim()
      : "";

  // Combine available components
  const parts = [desc, mfg, partNo].filter(Boolean);

  // If both mfg & partNo are missing and desc is empty, fall back to company
  if (parts.length === 0 && item.company && item.company.trim().toUpperCase() !== "NA") {
    parts.push(item.company.trim());
  }

  return parts.join(" ").trim();
}

/**
 * Generates an encoded Google search URL for a material item.
 * Returns null if no searchable information is available.
 */
export function getGoogleSearchUrl(item: MaterialQuerySource): string | null {
  const query = buildMaterialGoogleQuery(item);
  if (!query) return null;
  return `https://www.google.com/search?q=${encodeURIComponent(query)}`;
}

