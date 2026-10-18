// Swagger UI start-up for /docs (kept out of inline scripts because of the page's CSP)
window.ui = SwaggerUIBundle({
  url: "/openapi.json",
  dom_id: "#swagger-ui",
  deepLinking: true,
  persistAuthorization: true,
  presets: [SwaggerUIBundle.presets.apis],
  layout: "BaseLayout",
});
