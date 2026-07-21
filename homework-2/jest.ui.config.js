// Browser-level UI tests (npm run test:ui). Kept out of the main suite:
// they need a local Chrome/Chromium install and a spawned server.
module.exports = {
  testEnvironment: 'node',
  testMatch: ['<rootDir>/tests/ui/**/*.test.js'],
  testTimeout: 30000,
};
