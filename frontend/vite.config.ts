import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import adapter from 'svelte-adapter-bun';
import UnoCSS from 'unocss/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [
		UnoCSS(),
		sveltekit({ adapter: adapter({ out: 'build', precompress: true }) }),
		svelteTesting()
	],
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
		include: ['src/**/*.{test,spec}.{js,ts}', 'src/**/*.svelte.{test,spec}.ts'],
		server: {
			deps: {
				inline: ['zod']
			}
		}
	}
});
