import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import prettierConfig from 'eslint-config-prettier'
import globals from 'globals'

export default [
  js.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  prettierConfig,
  {
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.es2021,
      },
    },
    files: ['**/*.{js,vue}'],
    rules: {
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' }],
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      'no-debugger': 'warn',
      'vue/multi-word-component-names': 'off',
    },
  },
  {
    ignores: ['dist/', 'node_modules/', '*.config.js'],
  },
]
