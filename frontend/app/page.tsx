import HeroSection from "@/components/landing/HeroSection";
import FeatureCards from "@/components/landing/FeatureCards";
import AgentEconomySection from "@/components/landing/AgentEconomySection";
import TestimonialCarousel from "@/components/landing/TestimonialCarousel";
import FaqSection from "@/components/landing/FaqSection";
import CtaSection from "@/components/landing/CtaSection";
import Footer from "@/components/landing/Footer";

export default function Home() {
  return (
    <>
      <HeroSection />
      <FeatureCards />
      <AgentEconomySection />
      <TestimonialCarousel />
      <FaqSection />
      <CtaSection />
      <Footer />
    </>
  );
}
