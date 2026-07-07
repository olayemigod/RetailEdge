import { createApp } from 'vue';
import SalespersonPerformanceDashboard from './salesperson_performance_dashboard/SalespersonPerformanceDashboard.vue';

function mountSalespersonPerformanceDashboard(target) {
  const app = createApp(SalespersonPerformanceDashboard);
  const edgeUI = window.EdgeUI || {};
  const components = edgeUI.components || edgeUI;

  Object.entries(components).forEach(([name, component]) => {
    if (name.startsWith('Edge') && component) {
      app.component(name, component);
    }
  });

  app.mount(target);
  return app;
}

if (typeof window !== 'undefined') {
  window.SalespersonPerformanceDashboard = SalespersonPerformanceDashboard;
  window.mountSalespersonPerformanceDashboard = mountSalespersonPerformanceDashboard;
}

export { mountSalespersonPerformanceDashboard };
export default SalespersonPerformanceDashboard;
