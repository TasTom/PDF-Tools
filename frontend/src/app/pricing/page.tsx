const plans = [
  {
    name: 'Gratuit',
    price: '0',
    period: '',
    features: ['10 opérations/jour', 'Tous les outils PDF', 'Fichiers jusqu\'à 50MB', 'Pas d\'inscription requise'],
    cta: 'Commencer',
    popular: false,
  },
  {
    name: 'Pro',
    price: '5€',
    period: '/mois',
    features: ['500 opérations/jour', 'Tous les outils PDF', 'Fichiers jusqu\'à 200MB', 'API access', 'Support prioritaire', 'Batch processing'],
    cta: 'Devenir Pro',
    popular: true,
  },
];

export default function PricingPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-16">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold mb-4 bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
          Tarifs
        </h1>
        <p className="text-slate-400 text-lg">Commencez gratuitement, passez à Pro pour plus de puissance</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-3xl mx-auto">
        {plans.map(plan => (
          <div key={plan.name} className={`rounded-2xl border p-8 ${plan.popular ? 'border-blue-500 bg-blue-500/5 shadow-lg' : 'border-slate-700 bg-slate-900/50'}`}>
            {plan.popular && <div className="text-center mb-4"><span className="bg-blue-500 text-white text-xs px-3 py-1 rounded-full">Le plus populaire</span></div>}
            <h2 className="text-2xl font-bold text-white mb-2">{plan.name}</h2>
            <div className="mb-4"><span className="text-4xl font-bold text-white">{plan.price}</span><span className="text-slate-400">{plan.period}</span></div>
            <ul className="space-y-3 mb-8">
              {plan.features.map(f => <li key={f} className="flex items-center gap-2 text-slate-300"><span className="text-green-400">✓</span>{f}</li>)}
            </ul>
            <button className={`w-full py-3 rounded-xl font-semibold transition ${plan.popular ? 'bg-blue-600 hover:bg-blue-700 text-white' : 'bg-slate-700 hover:bg-slate-600 text-white'}`}>
              {plan.cta}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
