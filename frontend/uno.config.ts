import extractorSvelte from '@unocss/extractor-svelte';
import presetIcons from '@unocss/preset-icons';
import transformerVariantGroup from '@unocss/transformer-variant-group';
import { defineConfig, presetWind4 } from 'unocss';
import presetAnimations from 'unocss-preset-animations';
import { presetShadcn } from 'unocss-preset-shadcn';

export default defineConfig({
	extractors: [extractorSvelte()],
	presets: [
		presetWind4({ preflights: { reset: true } }),
		presetAnimations(),
		presetShadcn({ color: 'neutral', darkSelector: '.dark' }),
		presetIcons({ scale: 1.2 })
	],
	transformers: [transformerVariantGroup()],
	content: {
		pipeline: {
			include: [/\.(vue|svelte|[jt]sx|html)($|\?)/, '(components|src)/**/*.{js,ts}']
		}
	},
	theme: {
		// presetWind4 reads `font`, not `fontFamily`, and emits each stack as `--font-*`.
		font: {
			sans: '"IBM Plex Sans", ui-sans-serif, system-ui, sans-serif',
			mono: '"JetBrains Mono", "IBM Plex Mono", ui-monospace, monospace',
			display: '"JetBrains Mono", "IBM Plex Mono", ui-monospace, monospace'
		},
		colors: {
			// Control Room palette — reference CSS variables for dark/light switching
			'cr-bg': 'var(--cr-bg)',
			'cr-surface': 'var(--cr-surface)',
			'cr-border': 'var(--cr-border)',
			'cr-accent': 'var(--cr-accent)',
			'cr-accent-hover': 'var(--cr-accent-hover)',
			'cr-text': 'var(--cr-text)',
			'cr-text-muted': 'var(--cr-text-muted)',
			'cr-text-dim': 'var(--cr-text-dim)',
			// Status colors
			'cr-active': 'var(--cr-active)',
			'cr-pending': 'var(--cr-pending)',
			'cr-disabled': 'var(--cr-disabled)'
		}
	}
});
