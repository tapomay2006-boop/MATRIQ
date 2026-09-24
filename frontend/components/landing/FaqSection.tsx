"use client";

import { useState } from "react";
import { HelpCircle, Plus } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

type FaqItem = {
  question: string;
  answer: string;
};

const faqItems: FaqItem[] = [
  {
    question: "What is MATRIQ?",
    answer: "MATRIQ is an AI-powered platform that helps you standardize legacy descriptions, find equivalent materials across CPSEs, and enable faster procurement decisions.",
  },
  {
    question: "How does MATRIQ personalize recommendations?",
    answer: "MATRIQ analyzes legacy specifications, catalog entries, and procurement data to generate tailored insights that help you make smarter decisions.",
  },
  {
    question: "Is my data secure?",
    answer: "Yes. MATRIQ follows privacy-first principles with enterprise-grade encryption and secure authentication to protect your data.",
  },
  {
    question: "Can I connect multiple systems and catalogs?",
    answer: "Yes. MATRIQ is designed to provide a unified dashboard by securely connecting multiple data sources in one place.",
  },
  {
    question: "How does the AI explain its recommendations?",
    answer: "Every recommendation includes a clear explanation so you understand why a suggestion is made before taking action.",
  },
  {
    question: "Can I track standardization progress?",
    answer: "Absolutely. Monitor your progress, track matched items, and receive AI-powered suggestions to stay on track.",
  },
  {
    question: "Is MATRIQ suitable for beginners?",
    answer: "Yes. MATRIQ is built for everyone—from procurement officers and engineers to enterprise leaders—making material intelligence simple and easy to understand.",
  },
  {
    question: "What file formats are supported for catalog ingestion?",
    answer: "You can upload bulk catalogues in CSV, XLSX, and XLS formats, paste raw un-delimited ERP descriptions, or connect directly via our REST API.",
  },
];

export default function FaqSection() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  const toggleFaq = (index: number) => {
    setOpenIndex(openIndex === index ? null : index);
  };

  // Split items into 2 columns for desktop layout
  const leftColItems = faqItems.filter((_, i) => i % 2 === 0);
  const rightColItems = faqItems.filter((_, i) => i % 2 !== 0);

  return (
    <section
      id="faqs"
      className="relative w-full z-10 pt-16 pb-24 overflow-hidden scroll-mt-16"
      style={{
        backgroundColor: "#0A0809",
        backgroundImage:
          "radial-gradient(circle at 50% 0%, rgba(184,231,122,0.06), transparent 45%)",
      }}
    >
      <div className="max-w-[1200px] mx-auto px-6 xl:px-0 relative">
        <span id="faq" className="absolute -top-24 pointer-events-none" />
        {/* Header - matching Key Features style */}
        <div className="flex flex-col items-center text-center">
          {/* Tag / Pill Badge */}
          <div
            className="inline-flex items-center gap-2 rounded-full"
            style={{
              background: "rgba(255, 255, 255, 0.05)",
              backdropFilter: "blur(12px)",
              WebkitBackdropFilter: "blur(12px)",
              border: "1px solid rgba(255, 255, 255, 0.18)",
              color: "rgba(255, 255, 255, 0.75)",
              fontFamily: "var(--font-body)",
              height: "38px",
              padding: "8px 18px",
              fontSize: "12.5px",
              fontWeight: 500,
              letterSpacing: "0.02em",
              marginBottom: "20px",
              boxShadow: "0 2px 10px rgba(0, 0, 0, 0.2)",
            }}
          >
            <HelpCircle className="w-[14px] h-[14px] text-[#B8E77A]" />
            <span>Frequently Asked Questions</span>
          </div>

          {/* Heading */}
          <h2
            className="font-normal m-0 animate-fade-in"
            style={{
              fontFamily: "var(--font-heading)",
              fontSize: "clamp(32px, 5vw, 60px)",
              fontWeight: 400,
              lineHeight: 1.15,
              letterSpacing: "-0.03em",
              color: "#FFFFFF",
              marginBottom: "20px",
            }}
          >
            Frequently{" "}
            <span
              className="bg-clip-text text-transparent"
              style={{
                backgroundImage:
                  "linear-gradient(180deg, #E5ECCF 0%, #D4E0B0 35%, #C6DA93 65%, #A6C06B 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              Asked Questions
            </span>
          </h2>

          {/* Sub-heading */}
          <p
            className="font-normal mx-auto m-0"
            style={{
              fontFamily: "var(--font-body)",
              fontSize: "17.5px",
              fontWeight: 400,
              lineHeight: "28px",
              letterSpacing: "-0.01em",
              color: "rgba(255, 255, 255, 0.58)",
              maxWidth: "680px",
              marginTop: "0px",
              marginBottom: "56px",
            }}
          >
            Everything you need to know about MATRIQ, your AI-powered intelligence companion.
          </p>
        </div>

        {/* Two column FAQ layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 w-full items-start">
          {/* Left Column */}
          <div className="flex flex-col gap-6">
            {leftColItems.map((item, idx) => {
              const actualIndex = idx * 2;
              const isOpen = openIndex === actualIndex;
              return (
                <FaqCard
                  key={actualIndex}
                  item={item}
                  isOpen={isOpen}
                  onToggle={() => toggleFaq(actualIndex)}
                />
              );
            })}
          </div>

          {/* Right Column */}
          <div className="flex flex-col gap-6">
            {rightColItems.map((item, idx) => {
              const actualIndex = idx * 2 + 1;
              const isOpen = openIndex === actualIndex;
              return (
                <FaqCard
                  key={actualIndex}
                  item={item}
                  isOpen={isOpen}
                  onToggle={() => toggleFaq(actualIndex)}
                />
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

function FaqCard({ item, isOpen, onToggle }: { item: FaqItem; isOpen: boolean; onToggle: () => void }) {
  return (
    <motion.div
      layout
      className="border border-white/10 hover:border-[#B8E77A]/30 rounded-[20px] p-6 shadow-[0_4px_20px_rgba(0,0,0,0.3)] hover:-translate-y-0.5 transition-all duration-300 cursor-pointer overflow-hidden backdrop-blur-md"
      style={{
        background:
          "radial-gradient(circle at 80% 10%, rgba(184,231,122,0.06), transparent 35%), rgba(255,255,255,0.04)",
      }}
      onClick={onToggle}
    >
      <div className="flex justify-between items-center gap-4">
        <h4 className="text-lg font-semibold text-white tracking-tight leading-snug">
          {item.question}
        </h4>
        <div className="flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full bg-white/10 border border-white/15">
          <motion.div
            animate={{ rotate: isOpen ? 45 : 0 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
          >
            <Plus className="w-5 h-5 text-[#A8DD73]" />
          </motion.div>
        </div>
      </div>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <p className="pt-4 text-base text-white/60 leading-relaxed m-0">
              {item.answer}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
