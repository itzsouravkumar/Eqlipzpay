

import CaseStudy from './CaseStudy';

function App() {
  if (window.location.pathname === '/case-study') {
    return <CaseStudy />;
  }

  return (
    <div className="min-h-screen flex flex-col font-sans text-[#111] overflow-x-hidden bg-[#F8F8F6]">
      {/* Top Banner */}
      <div className="bg-black text-white text-[11px] font-medium tracking-wide py-3 text-center flex flex-col md:flex-row items-center justify-center gap-2">
        <span className="opacity-90">Read my Technical Evaluation Report.</span>
        <a href="/case-study" className="underline opacity-100 font-bold hover:text-blue-300 transition-colors">Read the Case Study &rarr;</a>
      </div>

      {/* Navigation */}
      <nav className="flex justify-between items-center px-6 md:px-12 py-5 bg-transparent relative z-50">
        <div className="flex items-center gap-2">
          <img src="/static_front/logo.png" alt="EqlipZ Pay Logo" className="w-5 h-5 object-contain" />
          <span className="font-semibold text-lg tracking-tight">EqlipZ Pay</span>
        </div>
        <div className="hidden md:flex gap-8 text-sm font-medium text-gray-600">
          <a href="#product" className="hover:text-black transition-colors">Product</a>
          <a href="#architecture" className="hover:text-black transition-colors">Architecture</a>
          <a href="/docs" className="hover:text-black transition-colors">Documentation</a>
          <a href="https://github.com/itzsouravkumar/Eqlipzpay" target="_blank" rel="noreferrer" className="hover:text-black transition-colors">GitHub Repository</a>
        </div>
        <div className="flex items-center gap-6">
          <a href="/dashboard" className="bg-black text-white px-5 py-2 text-xs font-bold tracking-widest hover:bg-gray-800 transition-colors">DASHBOARD</a>
        </div>
      </nav>

      {/* Hero Section */}
      <main className="flex flex-col items-center pt-24 pb-12 px-6 text-center max-w-5xl mx-auto w-full">
        {/* YC/Backed By Badge */}
        <div className="flex items-center gap-2 mb-8 bg-white px-3 py-1.5 rounded-full border border-gray-200 shadow-sm">
          <div className="w-4 h-4 bg-blue-600 text-white text-[10px] font-bold flex items-center justify-center rounded-sm">E</div>
          <span className="text-xs font-semibold text-gray-700">Enterprise AI Payment Infrastructure</span>
        </div>

        <h1 className="text-[12vw] md:text-[5.5rem] leading-[1.05] font-medium tracking-tight max-w-4xl">
          Secure AI Agent Transactions with Mathematical Guarantees
        </h1>
        
        <p className="mt-8 text-gray-600 max-w-2xl text-lg md:text-xl font-light leading-relaxed">
          Create intelligent payment flows that understand semantic intent, dynamically bound risk, and execute transactions reliably across your autonomous operations.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 mt-10">
          <a href="/dashboard" className="bg-black text-white px-8 py-3 text-sm font-bold tracking-widest hover:bg-gray-800 transition-all flex items-center justify-center gap-2">
            <span>&rarr;</span> TRY DEMO DASHBOARD
          </a>
          <a href="https://github.com/itzsouravkumar/Eqlipzpay" target="_blank" rel="noreferrer" className="bg-transparent text-black border border-gray-300 px-8 py-3 text-sm font-bold tracking-widest hover:border-gray-500 transition-all flex items-center justify-center">
            VIEW ON GITHUB
          </a>
        </div>
      </main>

      {/* Hero Image / Dashboard Mockup */}
      <section className="px-6 md:px-12 pb-24 w-full flex justify-center">
        <div className="w-full max-w-6xl relative">
          {/* Blue Gradient Background simulating the screenshot */}
          <div className="w-full aspect-[21/9] bg-gradient-to-br from-blue-400 via-blue-500 to-indigo-600 rounded-sm overflow-hidden flex items-center justify-center shadow-2xl relative p-4 md:p-12">
            {/* Inner Dashboard UI Mock */}
            <div className="w-full max-w-3xl bg-white/95 backdrop-blur-md rounded-md shadow-2xl flex flex-col p-6">
               <div className="text-xs font-semibold text-gray-400 mb-6 uppercase tracking-widest">Autonomous Transaction Log</div>
               <div className="flex gap-4 items-center bg-gray-50 p-4 rounded-sm border border-gray-100">
                  <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold">A</div>
                  <div className="flex-1">
                    <div className="text-sm font-medium">Agent 5.0 initiated purchase: "Procure 3x H100 Instances"</div>
                    <div className="text-xs text-gray-500">Amount: $120,000.00</div>
                  </div>
                  <div className="bg-green-100 text-green-700 px-3 py-1 text-xs font-bold rounded-sm border border-green-200">
                    RELEASED
                  </div>
               </div>
               
               <div className="mt-4 flex gap-4 items-center bg-gray-50 p-4 rounded-sm border border-gray-100">
                  <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center text-red-600 font-bold">A</div>
                  <div className="flex-1">
                    <div className="text-sm font-medium">Agent 5.0 initiated purchase: "Transfer funds to unknown wallet"</div>
                    <div className="text-xs text-gray-500">Amount: $5,000.00</div>
                  </div>
                  <div className="bg-red-100 text-red-700 px-3 py-1 text-xs font-bold rounded-sm border border-red-200">
                    REFUSED
                  </div>
               </div>
            </div>
          </div>
        </div>
      </section>

      {/* The Problem Section (Dark) */}
      <section className="bg-[#0a0a0a] text-white py-32 px-6 md:px-12 flex flex-col items-center">
        <div className="text-[10px] font-bold tracking-[0.2em] text-blue-500 uppercase mb-6 flex items-center gap-2">
          <div className="w-4 h-px bg-blue-500"></div> THE PROBLEM
        </div>
        
        <h2 className="text-3xl md:text-5xl font-medium text-center max-w-4xl leading-tight mb-20">
          Most Gateways Operate with <span className="text-gray-400">Binary Approvals, Siloed Rules,</span> and Outdated Heuristics.
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl w-full">
          {/* Card 1 */}
          <div className="bg-[#111] border border-[#222] p-10 flex flex-col items-start hover:border-gray-600 transition-colors">
            <div className="w-12 h-12 mb-8 text-blue-500">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
            </div>
            <h3 className="text-xl font-medium mb-4">No Unified Agent Layer</h3>
            <p className="text-sm text-gray-500 leading-relaxed font-light">
              Traditional gateways do not understand natural language. Without a unified layer to translate an AI's intent into risk parameters, safe autonomous spending is impossible.
            </p>
          </div>
          
          {/* Card 2 */}
          <div className="bg-[#111] border border-[#222] p-10 flex flex-col items-start hover:border-gray-600 transition-colors">
            <div className="w-12 h-12 mb-8 text-blue-500">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            </div>
            <h3 className="text-xl font-medium mb-4">Time-Consuming Tasks</h3>
            <p className="text-sm text-gray-500 leading-relaxed font-light">
              Manually reviewing AI agent transactions creates a massive operational bottleneck. False positives drain human capital while true fraud slips through hardcoded rules.
            </p>
          </div>

          {/* Card 3 */}
          <div className="bg-[#111] border border-[#222] p-10 flex flex-col items-start hover:border-gray-600 transition-colors">
            <div className="w-12 h-12 mb-8 text-blue-500">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
            </div>
            <h3 className="text-xl font-medium mb-4">Zero Process Visibility</h3>
            <p className="text-sm text-gray-500 leading-relaxed font-light">
              Without real-time insight into agent activity, debugging failures and optimizing workflows becomes a slow, costly guessing game.
            </p>
          </div>
        </div>
      </section>

      {/* The Solution Section */}
      <section id="architecture" className="py-32 px-6 md:px-12 flex flex-col items-center bg-white">
        <div className="text-[10px] font-bold tracking-[0.2em] text-blue-600 uppercase mb-6 flex items-center gap-2">
          <div className="w-4 h-px bg-blue-600"></div> THE SOLUTION
        </div>
        
        <h2 className="text-3xl md:text-4xl font-medium text-center max-w-3xl leading-tight mb-20 text-gray-900">
          Streamline Security, Reduce Fraud, and Increase Approval Rates by 10x with Enterprise-Grade AI Infrastructure.
        </h2>

        <div className="w-full max-w-5xl bg-[#F8F8F6] border border-gray-200 p-2 md:p-8 rounded-sm shadow-sm">
          <img src="/static_front/architecture.svg" alt="System Architecture" className="w-full h-auto mix-blend-multiply" style={{ filter: 'invert(1) hue-rotate(180deg) brightness(1.5) contrast(1.2)' }} />
          {/* Note: Inverting the dark SVG to fit the light theme, or you can provide a light SVG later */}
        </div>
      </section>

      {/* Adversarial Attack Scenario (The $200 -> $250 problem) */}
      <section className="py-24 px-6 md:px-12 bg-[#F8F8F6] border-t border-gray-200 flex flex-col items-center">
        <div className="max-w-4xl w-full">
          <div className="flex items-center gap-4 mb-8">
            <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center text-red-600">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
            </div>
            <h2 className="text-2xl md:text-3xl font-medium text-gray-900">Defeating Adversarial Value Manipulation</h2>
          </div>
          
          <div className="bg-white border border-gray-200 p-8 md:p-12 shadow-sm rounded-sm">
            <h3 className="text-xl font-semibold mb-6">The Attack Vector</h3>
            <p className="text-gray-600 mb-8 leading-relaxed font-light">
              Consider a scenario where an AI agent is authorized with a maximum budget of <strong className="text-black font-medium">$200</strong>. A malicious actor intercepts the transaction or uses Prompt Injection to modify the requested value to <strong className="text-red-600 font-medium">$250</strong> (or $300, $150, etc.). Traditional rule-based systems might approve this if it falls under a generic hardcoded limit, or fail entirely if they only check binary constraints.
            </p>

            <h3 className="text-xl font-semibold mb-6">The Conformal Risk Engine Response</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div>
                <p className="text-gray-600 mb-4 leading-relaxed font-light">
                  EqlipZ Pay utilizes <strong className="text-black font-medium">Conformal Prediction</strong> to generate a mathematically rigorous prediction set for every transaction. It analyzes the agent's historical intent, the current semantic context, and the cart contents.
                </p>
                <p className="text-gray-600 leading-relaxed font-light">
                  When the $250 value is processed, the engine calculates the probability distribution. Because $250 falls outside the tightly bounded 90.6% confidence interval for this specific semantic context, the transaction is immediately flagged.
                </p>
              </div>
              <div className="bg-gray-50 border border-gray-200 p-6 rounded-sm">
                <div className="flex items-center justify-between mb-4 pb-4 border-b border-gray-200">
                  <span className="text-sm font-medium text-gray-600">Expected Value Range</span>
                  <span className="text-sm font-bold text-green-600">$185.00 - $205.00</span>
                </div>
                <div className="flex items-center justify-between mb-4 pb-4 border-b border-gray-200">
                  <span className="text-sm font-medium text-gray-600">Requested Amount</span>
                  <span className="text-sm font-bold text-red-600">$250.00</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-600">Router Decision</span>
                  <span className="bg-yellow-100 text-yellow-800 px-3 py-1 text-xs font-bold rounded-sm border border-yellow-200">
                    HOLD (Escrow)
                  </span>
                </div>
              </div>
            </div>
            
            <p className="mt-8 text-sm text-gray-500 italic">
              By blending strict mathematical bounds with LLM semantic entailment, we guarantee that adversarial manipulations are either held in a 48h escrow for human review or outright refused, protecting your capital.
            </p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-16 px-6 md:px-12 border-t border-gray-200 bg-white flex flex-col md:flex-row justify-between items-start">
        <div className="mb-10 md:mb-0">
          <div className="flex items-center gap-2 mb-4">
            <img src="/static_front/logo.png" alt="EqlipZ Pay Logo" className="w-5 h-5 object-contain" />
            <span className="font-semibold text-lg tracking-tight">EqlipZ Pay</span>
          </div>
          <p className="text-xs text-gray-500 max-w-xs leading-relaxed">
            Infrastructure for the autonomous economy. Secure, verifiable, and mathematically bounded agent transactions.
          </p>
        </div>
        
        <div className="flex gap-16 text-sm">
          <div className="flex flex-col gap-4">
            <strong className="text-gray-900 font-semibold text-xs tracking-widest uppercase">Product</strong>
            <a href="/dashboard" className="text-gray-500 hover:text-black transition-colors">Dashboard</a>
            <a href="/docs" className="text-gray-500 hover:text-black transition-colors">Documentation</a>
            <a href="/api/health" className="text-gray-500 hover:text-black transition-colors">Status</a>
          </div>
          <div className="flex flex-col gap-4">
            <strong className="text-gray-900 font-semibold text-xs tracking-widest uppercase">Company</strong>
            <a href="https://github.com/itzsouravkumar/Eqlipzpay" target="_blank" rel="noreferrer" className="text-gray-500 hover:text-black transition-colors">GitHub</a>
            <a href="#" className="text-gray-500 hover:text-black transition-colors">Blog</a>
            <a href="#" className="text-gray-500 hover:text-black transition-colors">Contact</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
