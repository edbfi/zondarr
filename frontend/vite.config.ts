import { fileURLToPath } from 'node:url';
import adapter from '@sveltejs/adapter-bun';
import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import UnoCSS from 'unocss/vite';
import { defineConfig } from 'vitest/config';

// Tests that render components (by name, plus one plain .test.ts that renders).
const componentTests = [
	'src/**/*.svelte.{test,spec}.ts',
	'src/lib/components/wizard/__tests__/interactions.test.ts'
];

export default defineConfig({
	// SvelteKit 3 no longer generates $lib; tsconfig.json declares the same path.
	resolve: { alias: { $lib: fileURLToPath(new URL('./src/lib', import.meta.url)) } },
	plugins: [UnoCSS(), sveltekit({ adapter: adapter({ out: 'build', precompress: true }) })],
	optimizeDeps: {
		include: ['clsx', 'tailwind-merge', 'tailwind-variants', 'openapi-fetch', 'dompurify', 'marked']
	},
	server: {
		warmup: {
			clientFiles: [
				'src/routes/+layout.svelte',
				'src/routes/+page.svelte',
				'src/lib/api/client.ts',
				'src/app.css'
			]
		}
	},
	test: {
		environment: 'jsdom',
		setupFiles: ['./vitest-setup.ts'],
		server: {
			deps: {
				inline: ['zod']
			}
		},
		// Two projects: in SvelteKit 3 a server redirect() resolves through #internal with the
		// browser condition that svelteTesting() adds, so only the components project gets it.
		projects: [
			{
				extends: true,
				plugins: [svelteTesting()],
				test: { name: 'components', include: componentTests }
			},
			{
				extends: true,
				test: {
					name: 'server',
					include: ['src/**/*.{test,spec}.{js,ts}'],
					exclude: componentTests
				}
			}
		]
	}
});
