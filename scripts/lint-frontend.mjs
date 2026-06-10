#!/usr/bin/env node
import { execSync } from 'child_process'

const files = process.argv.slice(2).filter(f => f.startsWith('frontend/'))
if (!files.length) process.exit(0)

// Strip 'frontend/' prefix since cwd is set to 'frontend'
const relative = files.map(f => f.replace(/^frontend\//, ''))

execSync(`npx eslint --fix ${relative.join(' ')}`, {
  cwd: 'frontend',
  stdio: 'inherit',
})
