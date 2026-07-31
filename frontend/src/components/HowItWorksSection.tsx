import React from 'react';

const steps = [
  {
    number: "01",
    title: "Upload Syllabus",
    description: "Provide your course material in PDF or image format. The AI reads and understands your specific curriculum."
  },
  {
    number: "02",
    title: "Configure Exam",
    description: "Set total marks, duration, difficulty spread, and mandatory questions using our intuitive blueprint builder."
  },
  {
    number: "03",
    title: "Generate & Export",
    description: "Review the AI-generated questions, make any quick edits, and export directly to a formatted PDF."
  }
];

export function HowItWorksSection() {
  return (
    <section className="py-24 lg:py-32 bg-card border-y border-border">
      <div className="mx-auto max-w-7xl px-6 lg:px-12 xl:px-16">
        <div className="flex flex-col md:flex-row gap-12 lg:gap-24 items-center">
          
          {/* Left Text Block */}
          <div className="w-full md:w-5/12 space-y-6">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-secondary">
              Workflow
            </h2>
            <h3 className="text-3xl font-bold tracking-tight text-card-foreground sm:text-4xl">
              From raw syllabus to printed paper in minutes.
            </h3>
            <p className="text-lg text-muted-foreground leading-relaxed">
              We eliminated the manual drafting, the cognitive load of balancing difficulty, and the tedious formatting. Creating assessments has never been this streamlined.
            </p>
          </div>

          {/* Right Steps Block */}
          <div className="w-full md:w-7/12 relative">
            {/* Connecting line for desktop */}
            <div className="hidden md:block absolute left-8 top-8 bottom-8 w-px bg-border" />

            <div className="space-y-12">
              {steps.map((step, idx) => (
                <div key={idx} className="relative flex gap-6 items-start group">
                  <div className="relative z-10 flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-background border border-border shadow-sm text-xl font-bold text-primary transition-all duration-300 group-hover:scale-110 group-hover:border-primary/50 group-hover:shadow-md">
                    {step.number}
                  </div>
                  <div className="pt-3">
                    <h4 className="text-xl font-bold text-card-foreground mb-2">
                      {step.title}
                    </h4>
                    <p className="text-muted-foreground">
                      {step.description}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </section>
  );
}
