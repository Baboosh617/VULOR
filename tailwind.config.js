/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',  // all your HTML templates
    './static/js/**/*.js',    // any JS files using Tailwind classes
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};
