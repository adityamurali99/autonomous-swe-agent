const { normalizeUser } = require("../dist/index.js");

if (require.main === module) {
  process.stdout.write(normalizeUser(process.argv[2] || ""));
}

module.exports = { run: (name) => normalizeUser(name) };
