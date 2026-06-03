// ESLint 扁平配置（原型档：基础规则，含未用变量/import。合主干前再收紧）
import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    // 自动生成物禁止手改、不参与 lint（文件头标「自动生成，勿手改」）
    ignores: ["dist/**", "../../shared/contracts/**"],
  },
);
