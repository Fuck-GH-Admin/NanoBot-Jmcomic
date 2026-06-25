import os

def generate_tree(startpath):
    """生成文件树结构字符串"""
    tree_str = "Project Structure:\n"
    for root, dirs, files in os.walk(startpath):
        # 排除掉不需要的文件夹
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * level
        tree_str += f"{indent}{os.path.basename(root)}/\n"
        sub_indent = ' ' * 4 * (level + 1)
        for f in files:
            if f.endswith('.py') or f.endswith('.txt'):
                tree_str += f"{sub_indent}{f}\n"
    return tree_str

def merge_files(source_dir, output_filename, file_list):
    """将指定文件列表合并为一个大文件"""
    with open(output_filename, 'w', encoding='utf-8') as outfile:
        for file_path in file_list:
            relative_path = os.path.relpath(file_path, source_dir)
            outfile.write(f"\n\n{'#'*60}\n")
            outfile.write(f"### FILE: {relative_path}\n")
            outfile.write(f"{'#'*60}\n\n")
            try:
                with open(file_path, 'r', encoding='utf-8') as infile:
                    outfile.write(infile.read())
            except Exception as e:
                outfile.write(f"// 读取文件失败: {e}")
            outfile.write("\n")

def main():
    # --- 配置区域 ---
    target_dir = './chatbot'  # 你的插件目录
    output_dir = './packed_for_ai1'    # 打包后的存放位置
    # ----------------
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 1. 生成并保存文件树
    tree_content = generate_tree(target_dir)
    with open(os.path.join(output_dir, 'B_00_project_structure.txt'), 'w', encoding='utf-8') as f:
        f.write(tree_content)
    print("✅ 已生成文件树: B_00_project_structure.txt")

    # 2. 搜集所有 py 文件并分类
    handlers_files = []
    root_py_files = []

    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.endswith('.py') and '副本' not in file: # 自动排除副本
                full_path = os.path.join(root, file)
                if 'handlers' in root:
                    handlers_files.append(full_path)
                else:
                    root_py_files.append(full_path)

    # 3. 执行合并操作
    if root_py_files:
        merge_files(target_dir, os.path.join(output_dir, 'B_01_core_logic.txt'), root_py_files)
        print(f"✅ 已合并核心逻辑: B_01_core_logic.txt ({len(root_py_files)} 个文件)")

    if handlers_files:
        merge_files(target_dir, os.path.join(output_dir, 'B_02_handlers_logic.txt'), handlers_files)
        print(f"✅ 已合并处理器逻辑: B_02_handlers_logic.txt ({len(handlers_files)} 个文件)")

    print(f"\n🚀 完成！请将 {output_dir} 文件夹中的 txt 文件上传给 AI 即可。")

if __name__ == "__main__":
    main()