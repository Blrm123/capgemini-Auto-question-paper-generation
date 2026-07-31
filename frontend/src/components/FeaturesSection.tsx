import React from 'react';

const features = [
  {
    title: "Intelligent Syllabus Parsing",
    description: "Upload any unstructured syllabus PDF or image. Our AI extracts units, topics, and subtopics flawlessly.",
    icon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    )
  },
  {
    title: "Difficulty Balancing",
    description: "Automatically maps questions to Bloom's Taxonomy levels to ensure the perfect balance of easy, medium, and hard questions.",
    icon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
      </svg>
    )
  },
  {
    title: "Ready-to-Use Export",
    description: "Generate beautifully formatted examination papers instantly, ready to be printed or shared directly with students.",
    icon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
      </svg>
    )
  }
];

export function FeaturesSection() {
  return (
    <section className="relative py-24 lg:py-32 bg-background overflow-hidden">
      {/* Decorative background element */}
      <div className="absolute -top-24 left-1/2 -translate-x-1/2 w-[800px] h-[400px] opacity-20 bg-primary/30 blur-[120px] rounded-full pointer-events-none" />
      
      <div className="relative mx-auto max-w-7xl px-6 lg:px-12 xl:px-16">
        <div className="text-center max-w-3xl mx-auto mb-20">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-primary mb-3">
            Why QUBIT?
          </h2>
          <h3 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl lg:text-5xl">
            Everything you need to craft the perfect exam.
          </h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 lg:gap-12">
          {features.map((feature, idx) => (
            <div 
              key={idx}
              className="group relative flex flex-col items-start p-8 rounded-3xl bg-card border border-border/50 shadow-sm transition-all duration-300 hover:shadow-xl hover:-translate-y-1 hover:border-primary/20"
            >
              <div className="rounded-2xl bg-secondary/10 p-4 text-secondary mb-6 transition-colors duration-300 group-hover:bg-secondary group-hover:text-secondary-foreground">
                {feature.icon}
              </div>
              <h4 className="text-xl font-semibold text-card-foreground mb-3">
                {feature.title}
              </h4>
              <p className="text-muted-foreground leading-relaxed">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
