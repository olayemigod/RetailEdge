import { createApp } from "vue";
import BusinessControlCenter from "./business_control_center/BusinessControlCenter.vue";

window.retailedgeMountBusinessControlCenter = function mountBusinessControlCenter(wrapper) {
	const root = document.createElement("div");
	root.className = "retailedge-business-control-center-root";
	wrapper.querySelector(".layout-main-section")?.appendChild(root);
	createApp(BusinessControlCenter).mount(root);
};
