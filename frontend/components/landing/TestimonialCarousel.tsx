"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Star, User, Users, Quote, MessageSquare, Send, Upload, Image as ImageIcon, ShieldCheck } from "lucide-react";

// Predefined avatar options
const predefinedAvatars = [
  "https://i.pravatar.cc/150?img=1",
  "https://i.pravatar.cc/150?img=2",
  "https://i.pravatar.cc/150?img=3",
  "https://i.pravatar.cc/150?img=5",
  "https://i.pravatar.cc/150?img=7",
  "https://i.pravatar.cc/150?u=ananya",
  "https://i.pravatar.cc/150?img=9",
  "https://i.pravatar.cc/150?img=12",
];

const defaultTestimonials = [
  {
    name: "Alex R.",
    country: "Procurement Specialist",
    type: "Enterprise",
    avatar: "https://i.pravatar.cc/150?img=11",
    feedback: "MATRIQ made catalog standardization feel effortless. The AI suggestions were simple, practical, and highly accurate.",
    rating: 5,
  },
  {
    name: "Sarah L.",
    country: "Supply Chain Lead",
    type: "Lead",
    avatar: "https://i.pravatar.cc/150?img=5",
    feedback: "We finally eliminated duplicate descriptions across our CPSE branches. The explainable AI insights make every match easy to trust.",
    rating: 5,
  },
  {
    name: "Daniel K.",
    country: "Materials Engineer",
    type: "Engineer",
    avatar: "https://i.pravatar.cc/150?img=3",
    feedback: "Having all inventory records and harmonized specifications in one dashboard has completely changed how we procure.",
    rating: 5,
  },
  {
    name: "Priya M.",
    country: "Procurement Analyst",
    type: "Analyst",
    avatar: "https://i.pravatar.cc/150?img=9",
    feedback: "The automated material equivalence suggestions helped us find stock across sister CPSEs without delay.",
    rating: 5,
  },
  {
    name: "Ethan C.",
    country: "Business Analyst",
    type: "Analyst",
    avatar: "https://i.pravatar.cc/150?img=8",
    feedback: "Unlike traditional catalog matching tools, MATRIQ explains every recommendation instead of expecting us to trust a black box.",
    rating: 5,
  },
  {
    name: "Maya T.",
    country: "Operations Consultant",
    type: "Consultant",
    avatar: "https://i.pravatar.cc/150?img=7",
    feedback: "The clean interface and intelligent categorization tools make material harmonization surprisingly seamless.",
    rating: 5,
  },
  {
    name: "Jordan W.",
    country: "Inventory Lead",
    type: "Manager",
    avatar: "https://i.pravatar.cc/150?img=12",
    feedback: "Secure, transparent, and genuinely useful. MATRIQ feels like having a specialized material intelligence partner available anytime.",
    rating: 5,
  },
];

const avatars = [
  {
    imageUrl: "https://avatars.githubusercontent.com/u/16860528",
    profileUrl: "https://github.com/dillionverma",
  },
  {
    imageUrl: "https://avatars.githubusercontent.com/u/20110627",
    profileUrl: "https://github.com/tomonarifeehan",
  },
  {
    imageUrl: "https://avatars.githubusercontent.com/u/106103625",
    profileUrl: "https://github.com/BankkRoll",
  },
  {
    imageUrl: "https://avatars.githubusercontent.com/u/59228569",
    profileUrl: "https://github.com/safethecode",
  },
  {
    imageUrl: "https://avatars.githubusercontent.com/u/59442788",
    profileUrl: "https://github.com/sanjay-mali",
  },
  {
    imageUrl: "https://avatars.githubusercontent.com/u/89768406",
    profileUrl: "https://github.com/itsarghyadas",
  },
];

function cn(...classes: Array<string | undefined | null | false>) {
  return classes.filter(Boolean).join(" ");
}

function AvatarCircles({ numPeople, avatarUrls }: { numPeople: number; avatarUrls: { imageUrl: string; profileUrl: string }[] }) {
  return (
    <div className="flex items-center justify-center -space-x-3">
      {avatarUrls.map((avatar, idx) => (
        <a
          key={idx}
          href={avatar.profileUrl}
          target="_blank"
          rel="noreferrer"
          className="h-10 w-10 rounded-full border-2 border-white overflow-hidden hover:z-10 transition-transform hover:scale-110"
        >
          <img src={avatar.imageUrl} alt="" className="h-full w-full object-cover" />
        </a>
      ))}
      {numPeople && (
        <div className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-white bg-black text-xs font-semibold text-white">
          +{numPeople}
        </div>
      )}
    </div>
  );
}

export default function TestimonialCarousel() {
  const [testimonials, setTestimonials] = useState(defaultTestimonials);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [selectedAvatar, setSelectedAvatar] = useState<string | null>(null);
  const [customImage, setCustomImage] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    name: "",
    occupation: "",
    primaryUse: "",
    frequency: "",
    feedback: "",
    rating: 5,
    favoriteFeature: "",
    allowPublic: false,
    avatar: null as string | null,
  });

  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const fetchTestimonials = async () => {
      try {
        const response = await fetch("/api/testimonials");
        if (response.ok) {
          const contentType = response.headers.get("content-type");
          if (contentType && contentType.includes("application/json")) {
            const data = await response.json();
            if (data.success && data.data.length > 0) {
              setTestimonials(data.data);
            }
          }
        }
      } catch (error) {
        // Fall back silently to default local testimonials
      }
    };
    fetchTestimonials();
  }, []);

  const row1Testimonials = testimonials.filter((_, i) => i % 2 === 0);
  const row2Testimonials = testimonials.filter((_, i) => i % 2 !== 0);

  const row1All = [...row1Testimonials, ...row1Testimonials];
  const row2All = [...row2Testimonials, ...row2Testimonials];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      const response = await fetch("/api/testimonials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const contentType = response.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        const data = await response.json();
        if (data.success) {
          setStatusMessage({
            type: "success",
            message: "Thank you! Your feedback helps us build a smarter material harmonization experience for everyone.",
          });
          setFormData({
            name: "",
            occupation: "",
            primaryUse: "",
            frequency: "",
            feedback: "",
            rating: 5,
            favoriteFeature: "",
            allowPublic: false,
            avatar: null,
          });
          setSelectedAvatar(null);
          setCustomImage(null);

          const refreshResponse = await fetch("/api/testimonials");
          const refreshContentType = refreshResponse.headers.get("content-type");
          if (refreshResponse.ok && refreshContentType && refreshContentType.includes("application/json")) {
            const refreshData = await refreshResponse.json();
            if (refreshData.success) {
              setTestimonials(refreshData.data);
            }
          }

          setTimeout(() => {
            setIsModalOpen(false);
            setStatusMessage(null);
          }, 2000);
        } else {
          setStatusMessage({ type: "error", message: data.error || "Failed to submit" });
        }
      } else {
        throw new Error("Response was not JSON");
      }
    } catch (error) {
      console.error("Error submitting testimonial:", error);
      // Fallback add on client side for demo
      const newTestimonial = {
        name: formData.name || "Anonymous",
        country: formData.occupation || "User",
        type: formData.primaryUse || "Feedback",
        avatar: formData.avatar || `https://i.pravatar.cc/150?img=${Math.floor(Math.random() * 12 + 1)}`,
        feedback: formData.feedback,
        rating: formData.rating,
      };
      if (formData.allowPublic) {
        setTestimonials((prev) => [newTestimonial, ...prev]);
      }
      setStatusMessage({ type: "success", message: "Thank you! Your feedback helps us build a smarter material harmonization experience for everyone." });
      setTimeout(() => {
        setIsModalOpen(false);
        setStatusMessage(null);
      }, 2000);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section
      id="reviews"
      className="relative w-full z-10 pt-16 pb-20 overflow-hidden scroll-mt-16"
      style={{
        backgroundColor: "#0A0809",
        backgroundImage: `
          radial-gradient(circle at 50% 0%, rgba(184,231,122,0.06), transparent 45%),
          linear-gradient(to right, rgba(255, 255, 255, 0.03) 1px, transparent 1px),
          linear-gradient(to bottom, rgba(255, 255, 255, 0.03) 1px, transparent 1px)
        `,
        backgroundSize: "100% 100%, 36px 36px, 36px 36px",
      }}
    >
      <div className="max-w-[1200px] mx-auto px-6 xl:px-0 relative">
        <span id="testimonials" className="absolute -top-24 pointer-events-none" />
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
            <Users className="w-[14px] h-[14px] text-[#B8E77A]" />
            <span>Trusted by CPSE Experts</span>
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
            Trusted by Experts{" "}
            <span
              className="bg-clip-text text-transparent"
              style={{
                backgroundImage:
                  "linear-gradient(180deg, #E5ECCF 0%, #D4E0B0 35%, #C6DA93 65%, #A6C06B 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              Building a Unified Future
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
              maxWidth: "760px",
              marginTop: "0px",
              marginBottom: "48px",
            }}
          >
            Hear from CPSE stakeholders and domain experts on how NEMISYS is simplifying material standardization and enabling smarter procurement.
          </p>

          {/* Avatars Circles */}
          <div className="flex flex-col items-center gap-4 mb-12">
            <AvatarCircles numPeople={30} avatarUrls={avatars} />
          </div>
        </div>
      </div>

      {/* Sliding testimonials marquee (2 rows) */}
      <div className="relative overflow-hidden w-full py-4 mb-8 flex flex-col gap-6">
        <div className="pointer-events-none absolute left-0 top-0 bottom-0 w-32 bg-gradient-to-r from-[#0A0809] to-transparent z-10" />
        <div className="pointer-events-none absolute right-0 top-0 bottom-0 w-32 bg-gradient-to-l from-[#0A0809] to-transparent z-10" />

        {/* Row 1: Sliding Left */}
        <div className="flex animate-marquee hover:pause-marquee" style={{ width: "max-content" }}>
          {row1All.map((testimonial, index) => (
            <div key={`row1-${index}`} className="px-4 flex-shrink-0" style={{ width: "450px" }}>
              <TestimonialCard testimonial={testimonial} />
            </div>
          ))}
        </div>

        {/* Row 2: Sliding Right */}
        <div className="flex animate-marquee-reverse hover:pause-marquee" style={{ width: "max-content" }}>
          {row2All.map((testimonial, index) => (
            <div key={`row2-${index}`} className="px-4 flex-shrink-0" style={{ width: "450px" }}>
              <TestimonialCard testimonial={testimonial} />
            </div>
          ))}
        </div>
      </div>

      <div className="flex justify-center mt-6">
        <button
          onClick={() => setIsModalOpen(true)}
          className="h-12 px-8 rounded-full bg-[#A8DD73] text-[#0A0809] hover:bg-[#B8E77A] font-semibold text-base transition-all duration-300 shadow-[0_4px_16px_rgba(168,221,115,0.25)] hover:-translate-y-0.5 cursor-pointer"
          style={{ fontFamily: "var(--font-body)" }}
        >
          Share Your Experience
        </button>
      </div>

      {/* Lightweight Custom Modal */}
      {isModalOpen && mounted && createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
          <div className="relative w-full max-w-[550px] max-h-[85vh] bg-[#121011] border border-white/10 rounded-3xl p-8 shadow-2xl overflow-hidden flex flex-col animate-scale-up text-left">
            <button
              onClick={() => {
                setIsModalOpen(false);
                setStatusMessage(null);
              }}
              className="absolute top-6 right-6 text-white/40 hover:text-white font-semibold text-lg cursor-pointer"
            >
              ✕
            </button>

            <div className="flex flex-col gap-1 mb-6 pr-6">
              <h3 className="text-2xl font-bold text-white flex items-center gap-2">
                <ShieldCheck className="w-6 h-6 text-[#A8DD73]" />
                Share Your Experience
              </h3>
              <p className="text-white/60 text-sm">
                Tell us how our platform helped your team standardize and streamline material procurement.
              </p>
            </div>

            <div className="overflow-y-auto flex-1 pr-1 space-y-4">
              {statusMessage && (
                <div
                  className={`p-4 rounded-xl border ${statusMessage.type === "success"
                    ? "bg-[#A8DD73]/10 border-[#A8DD73]/30 text-[#A8DD73]"
                    : "bg-red-500/10 border-red-500/30 text-red-400"
                    } flex items-center gap-3`}
                >
                  <p className="font-medium text-sm">{statusMessage.message}</p>
                </div>
              )}

              {!statusMessage && (
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-sm font-semibold text-white/80">
                      Overall Experience <span className="text-[#A8DD73]">*</span>
                    </label>
                    <div className="flex gap-2">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <button
                          key={star}
                          type="button"
                          onClick={() => setFormData({ ...formData, rating: star })}
                          className="transition-transform hover:scale-110 cursor-pointer"
                        >
                          <Star
                            className={`h-8 w-8 cursor-pointer ${star <= formData.rating
                              ? "fill-[#A8DD73] text-[#A8DD73]"
                              : "fill-none text-white/20 hover:text-white/40"
                              }`}
                          />
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-3">
                    <label className="text-sm font-semibold text-white/80">
                      Profile Image <span className="text-white/40 font-normal">(Optional)</span>
                    </label>

                    <div className="flex items-center gap-4">
                      <div className="relative w-16 h-16 rounded-2xl border border-white/10 bg-white/5 overflow-hidden flex items-center justify-center">
                        {customImage || selectedAvatar ? (
                          <img src={customImage || selectedAvatar || ""} alt="Preview" className="w-full h-full object-cover" />
                        ) : (
                          <ImageIcon className="w-6 h-6 text-white/40" />
                        )}
                      </div>
                      <div className="flex-1">
                        <p className="text-xs text-white/50 mb-2">Choose from avatars or upload your own</p>
                        <div className="flex gap-2">
                          <label className="cursor-pointer">
                            <input
                              type="file"
                              accept="image/*"
                              className="hidden"
                              onChange={(e) => {
                                const file = e.target.files?.[0];
                                if (file) {
                                  const reader = new FileReader();
                                  reader.onloadend = () => {
                                    const base64String = reader.result as string;
                                    setCustomImage(base64String);
                                    setFormData({ ...formData, avatar: base64String });
                                  };
                                  reader.readAsDataURL(file);
                                }
                              }}
                            />
                            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#A8DD73]/15 border border-[#A8DD73]/30 hover:bg-[#A8DD73]/25 transition-colors text-[#A8DD73] text-xs font-semibold cursor-pointer">
                              <Upload className="w-3.5 h-3.5" />
                              Upload Image
                            </div>
                          </label>
                          {customImage && (
                            <button
                              type="button"
                              onClick={() => {
                                setCustomImage(null);
                                setFormData({ ...formData, avatar: selectedAvatar });
                              }}
                              className="px-3 py-1.5 text-xs rounded-lg border border-red-500/30 bg-red-500/15 hover:bg-red-500/25 text-red-400 font-semibold cursor-pointer"
                            >
                              Remove
                            </button>
                          )}
                        </div>
                      </div>
                    </div>

                    {!customImage && (
                      <div>
                        <p className="text-[10px] text-white/40 uppercase tracking-wider mb-2">Or choose an avatar:</p>
                        <div className="grid grid-cols-8 gap-2">
                          {predefinedAvatars.map((avatar, index) => (
                            <button
                              key={index}
                              type="button"
                              onClick={() => {
                                setSelectedAvatar(avatar);
                                setFormData({ ...formData, avatar });
                              }}
                              className={`w-10 h-10 rounded-xl overflow-hidden border-2 transition-all hover:scale-110 cursor-pointer ${selectedAvatar === avatar ? "border-[#A8DD73] ring-2 ring-[#A8DD73]/30" : "border-white/10 hover:border-white/30"
                                }`}
                            >
                              <img src={avatar} alt={`Avatar ${index + 1}`} className="w-full h-full object-cover" />
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="space-y-1">
                    <label htmlFor="name" className="text-xs font-semibold text-white/80">
                      Your Name <span className="text-[#A8DD73]">*</span>
                    </label>
                    <input
                      id="name"
                      type="text"
                      placeholder="Enter your full name"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      required
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-xl text-white placeholder:text-white/30 focus:outline-none focus:border-[#A8DD73] text-sm"
                    />
                  </div>

                  <div className="space-y-1">
                    <label htmlFor="occupation" className="text-xs font-semibold text-white/80">
                      Your Role <span className="text-[#A8DD73]">*</span>
                    </label>
                    <select
                      id="occupation"
                      value={formData.occupation}
                      onChange={(e) => setFormData({ ...formData, occupation: e.target.value })}
                      required
                      className="w-full px-3 py-2 bg-[#1b191a] border border-white/10 rounded-xl text-white focus:outline-none focus:border-[#A8DD73] text-sm"
                    >
                      <option value="">Select your role</option>
                      <option value="Procurement / Purchase">Procurement / Purchase</option>
                      <option value="Materials Management">Materials Management</option>
                      <option value="Engineering / Technical">Engineering / Technical</option>
                      <option value="Inventory / Stores">Inventory / Stores</option>
                      <option value="Technical Committee">Technical Committee</option>
                      <option value="IT / Digital Transformation">IT / Digital Transformation</option>
                      <option value="Management">Management</option>
                      <option value="Other">Other</option>
                    </select>
                  </div>

                  <div className="space-y-1">
                    <label htmlFor="primaryUse" className="text-xs font-semibold text-white/80">
                      Primary Use <span className="text-[#A8DD73]">*</span>
                    </label>
                    <select
                      id="primaryUse"
                      value={formData.primaryUse}
                      onChange={(e) => setFormData({ ...formData, primaryUse: e.target.value })}
                      required
                      className="w-full px-3 py-2 bg-[#1b191a] border border-white/10 rounded-xl text-white focus:outline-none focus:border-[#A8DD73] text-sm"
                    >
                      <option value="">Select primary use case</option>
                      <option value="Find Equivalent Materials">Find Equivalent Materials</option>
                      <option value="Standardize Material Descriptions">Standardize Material Descriptions</option>
                      <option value="Search Material Catalogs">Search Material Catalogs</option>
                      <option value="Verify Material Matches">Verify Material Matches</option>
                      <option value="Review AI Recommendations">Review AI Recommendations</option>
                      <option value="Create / Update Material Masters">Create / Update Material Masters</option>
                      <option value="Analyze Legacy Material Data">Analyze Legacy Material Data</option>
                      <option value="Other">Other</option>
                    </select>
                  </div>

                  <div className="space-y-1">
                    <label htmlFor="frequency" className="text-xs font-semibold text-white/80">
                      How often do you use the platform? <span className="text-[#A8DD73]">*</span>
                    </label>
                    <select
                      id="frequency"
                      value={formData.frequency}
                      onChange={(e) => setFormData({ ...formData, frequency: e.target.value })}
                      required
                      className="w-full px-3 py-2 bg-[#1b191a] border border-white/10 rounded-xl text-white focus:outline-none focus:border-[#A8DD73] text-sm"
                    >
                      <option value="">Select frequency</option>
                      <option value="Daily">Daily</option>
                      <option value="Several times a week">Several times a week</option>
                      <option value="Weekly">Weekly</option>
                      <option value="Occasionally">Occasionally</option>
                      <option value="Currently evaluating">Currently evaluating</option>
                      <option value="First-time user">First-time user</option>
                    </select>
                  </div>

                  <div className="space-y-1">
                    <label htmlFor="favoriteFeature" className="text-xs font-semibold text-white/80">
                      Most Useful Feature <span className="text-white/40 font-normal">(Optional)</span>
                    </label>
                    <select
                      id="favoriteFeature"
                      value={formData.favoriteFeature}
                      onChange={(e) => setFormData({ ...formData, favoriteFeature: e.target.value })}
                      className="w-full px-3 py-2 bg-[#1b191a] border border-white/10 rounded-xl text-white focus:outline-none focus:border-[#A8DD73] text-sm"
                    >
                      <option value="">Select a feature</option>
                      <option value="AI Attribute Extraction">AI Attribute Extraction</option>
                      <option value="Semantic Material Search">Semantic Material Search</option>
                      <option value="Equivalent Material Matching">Equivalent Material Matching</option>
                      <option value="Match Confidence & Ranking">Match Confidence & Ranking</option>
                      <option value="Expert Review & Approval">Expert Review & Approval</option>
                      <option value="Unified Material Master">Unified Material Master</option>
                    </select>
                  </div>

                  <div className="space-y-1">
                    <label htmlFor="feedback" className="text-xs font-semibold text-white/80">
                      Share Your Experience <span className="text-[#A8DD73]">*</span>
                    </label>
                    <textarea
                      id="feedback"
                      placeholder="Share how NEMISYS helped simplify material search, matching, or standardization."
                      value={formData.feedback}
                      onChange={(e) => setFormData({ ...formData, feedback: e.target.value })}
                      required
                      rows={3}
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-xl text-white placeholder:text-white/30 focus:outline-none focus:border-[#A8DD73] text-sm resize-none"
                    />
                  </div>

                  <div className="flex items-center gap-2 py-1">
                    <input
                      id="allowPublic"
                      type="checkbox"
                      checked={formData.allowPublic}
                      onChange={(e) => setFormData({ ...formData, allowPublic: e.target.checked })}
                      className="w-4 h-4 rounded border-white/20 bg-white/5 text-[#A8DD73] focus:ring-[#A8DD73]"
                    />
                    <label htmlFor="allowPublic" className="text-xs font-medium text-white/60 cursor-pointer">
                      I agree to let the platform display my feedback publicly.
                    </label>
                  </div>

                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="w-full h-12 rounded-full bg-[#A8DD73] text-[#0A0809] hover:bg-[#B8E77A] font-semibold text-base flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all cursor-pointer shadow-[0_4px_16px_rgba(168,221,115,0.25)]"
                  >
                    {isSubmitting ? "Submitting..." : "Submit Feedback"}
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}

      <style jsx global>{`
        @keyframes marquee {
          0% {
            transform: translateX(0);
          }
          100% {
            transform: translateX(-50%);
          }
        }
        @keyframes marquee-reverse {
          0% {
            transform: translateX(-50%);
          }
          100% {
            transform: translateX(0);
          }
        }
        .animate-marquee {
          animation: marquee 30s linear infinite;
        }
        .animate-marquee:hover {
          animation-play-state: paused;
        }
        .animate-marquee-reverse {
          animation: marquee-reverse 30s linear infinite;
        }
        .animate-marquee-reverse:hover {
          animation-play-state: paused;
        }
      `}</style>
    </section>
  );
}

function TestimonialCard({ testimonial }: { testimonial: any }) {
  return (
    <div
      className="relative group transition-all duration-300 h-full border border-white/10 hover:border-[#B8E77A]/30 hover:shadow-[0_12px_30px_-10px_rgba(0,0,0,0.6)] hover:-translate-y-1 rounded-[24px] overflow-hidden backdrop-blur-md text-left flex flex-col justify-between"
      style={{
        minHeight: "260px",
        background:
          "radial-gradient(circle at 80% 10%, rgba(184,231,122,0.06), transparent 35%), rgba(255,255,255,0.04)",
      }}
    >
      <div className="absolute top-0 right-0 p-6 text-white/5 group-hover:text-[#A8DD73]/15 transition-colors">
        <Quote className="w-12 h-12 rotate-180" />
      </div>

      <div className="p-7 flex flex-col h-full relative z-10 justify-between flex-grow">
        <div>
          <div className="flex items-center space-x-4 mb-5">
            {testimonial.avatar ? (
              <div className="relative">
                <img
                  src={testimonial.avatar || "/placeholder.svg"}
                  alt={testimonial.name}
                  className="w-13 h-13 rounded-2xl border border-white/15 object-cover"
                />
                <div className="absolute -bottom-1 -right-1 w-3.5 h-3.5 bg-[#A8DD73] rounded-full border-2 border-[#0A0809]" />
              </div>
            ) : (
              <div className="w-13 h-13 rounded-2xl bg-white/10 flex items-center justify-center border border-white/15">
                <User className="w-6 h-6 text-[#A8DD73]" />
              </div>
            )}
            <div>
              <h4 className="font-semibold text-white text-base tracking-tight">{testimonial.name}</h4>
              <p className="text-xs font-medium uppercase tracking-widest text-[#A8DD73]">{testimonial.country}</p>
            </div>
          </div>

          <p className="text-white/70 text-[15px] leading-relaxed flex-grow mb-5 group-hover:text-white transition-colors italic">
            &quot;{testimonial.feedback}&quot;
          </p>
        </div>

        <div className="flex justify-between items-center mt-auto pt-4 border-t border-white/10">
          <div className="flex space-x-1">
            {[1, 2, 3, 4, 5].map((star) => (
              <Star
                key={star}
                className={`h-3.5 w-3.5 ${star <= (testimonial.rating || 5) ? "fill-[#A8DD73] text-[#A8DD73]" : "fill-none text-white/20"
                  }`}
              />
            ))}
          </div>
          <span className="px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-wider rounded-full bg-white/10 text-white/70 border border-white/15 group-hover:border-[#B8E77A]/30 group-hover:text-[#A8DD73] transition-all">
            {testimonial.type}
          </span>
        </div>
      </div>
    </div>
  );
}
