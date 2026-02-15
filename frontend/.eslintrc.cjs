module.exports = {
  root: true,
  env: {
    browser: true,
    es2022: true,
    node: true
  },
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
    project: ["./tsconfig.json", "./tsconfig.node.json"]
  },
  plugins: ["@typescript-eslint", "react-hooks", "import", "security"],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended-type-checked",
    "plugin:@typescript-eslint/stylistic-type-checked",
    "plugin:react-hooks/recommended",
    "plugin:import/recommended",
    "plugin:import/typescript",
    "plugin:security/recommended-legacy",
    "prettier"
  ],
  settings: {
    "import/resolver": {
      typescript: {
        alwaysTryTypes: true,
        project: "./tsconfig.json"
      }
    }
  },
  ignorePatterns: ["dist", "coverage", "node_modules"],
  rules: {
    "@typescript-eslint/consistent-type-imports": [
      "error",
      {
        prefer: "type-imports"
      }
    ],
    "@typescript-eslint/no-floating-promises": "error",
    "@typescript-eslint/no-misused-promises": "error",
    "@typescript-eslint/no-unused-vars": [
      "error",
      {
        argsIgnorePattern: "^_"
      }
    ],
    "import/no-default-export": "off",
    "import/no-restricted-paths": [
      "error",
      {
        zones: [
          {
            target: "./src/domain",
            from: "./src/adapters"
          },
          {
            target: "./src/domain",
            from: "./src/infrastructure"
          },
          {
            target: "./src/application",
            from: "./src/adapters"
          },
          {
            target: "./src/application",
            from: "./src/infrastructure"
          },
          {
            target: "./src/ports",
            from: "./src/adapters/inbound"
          },
          {
            target: "./src/ports",
            from: "./src/infrastructure"
          },
          {
            target: "./src/adapters/outbound",
            from: "./src/adapters/inbound"
          }
        ]
      }
    ]
  },
  overrides: [
    {
      files: ["src/**/*.test.ts", "src/**/*.test.tsx"],
      rules: {
        "@typescript-eslint/require-await": "off",
        "@typescript-eslint/no-unsafe-assignment": "off",
        "@typescript-eslint/no-unsafe-member-access": "off",
        "@typescript-eslint/no-unsafe-call": "off"
      }
    }
  ]
};
