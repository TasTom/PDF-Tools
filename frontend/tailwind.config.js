/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],

  // Palette volontairement FERMEE : `theme.colors` remplace les jetons Tailwind
  // au lieu de les etendre. Aucune classe generique (slate, indigo, blue, ...)
  // ne compile plus, donc aucun retour au theme par defaut n'est possible sans
  // repasser par ce fichier. Toute couleur doit etre nommee ici.
  theme: {
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      inherit: 'inherit',
      white: '#FFFFFF',

      // Surfaces : papier froid, jamais creme (tell n.1 des pages generees).
      paper: '#FAFAF8',
      sunk: '#F2F1EB',

      // Encre d'impression, bleu-noir et non noir pur.
      ink: '#14181F',
      'ink-soft': '#4A5260', // texte secondaire : 7,5:1 sur le papier
      'ink-faint': '#676E79', // texte tertiaire : 4,9:1, AA respecte
                             // (#6E7681 tombait a 4,40:1, sous le seuil)

      rule: '#E4E2DA', // filets de separation

      // Accent unique : rouge de correction, utilise UNIQUEMENT pour signaler
      // un etat (focus, page courante, traitement, erreur, succes) ou ce qu'une
      // operation ajoute au document. Jamais en aplat decoratif.
      accent: '#A32B1C',
      'accent-soft': '#FAEEEB',
      good: '#1B6046',
    },

    // Les bordures par defaut pointaient sur `gray-200`, retire ci-dessus :
    // on les rattache explicitement au filet de la palette.
    borderColor: ({ theme }) => ({ ...theme('colors'), DEFAULT: theme('colors.rule') }),
    ringColor: ({ theme }) => ({ ...theme('colors'), DEFAULT: theme('colors.accent') }),

    extend: {
      fontFamily: {
        sans: ['var(--font-sans)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'ui-monospace', 'monospace'],
      },
      maxWidth: {
        measure: '64ch', // longueur de ligne confortable pour la lecture
      },
    },
  },

  plugins: [],
};
