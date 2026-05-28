"""
RG数据清洗主程序
功能：将ASEData/RG目录下的所有xlsx文件清洗整理成统一格式的RG数据文件
输出：RG_[时间戳].xlsx 文件，包含三列：NUM, lot_ID, RG(R)
"""

import pandas as pd
import re
from pathlib import Path
from datetime import datetime
import logging
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from excel_utils import generate_lot_based_filename, read_excel_fast, write_excel_fast

class RGCleaner:
    """RG数据清洗器"""
    
    def __init__(self, input_dir="../ASEData/RG", output_dir="../output"):
        """
        初始化RG清洗器
        
        Args:
            input_dir: RG源数据目录
            output_dir: 输出目录
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.setup_logging()
        
    def setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('rg_cleaner.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def scan_rg_files(self):
        """扫描RG目录下的所有xlsx文件"""
        self.logger.info(f"开始扫描RG文件目录: {self.input_dir}")
        
        if not self.input_dir.exists():
            self.logger.error(f"RG目录不存在: {self.input_dir}")
            return []
        
        # 获取所有xlsx文件，排除临时文件
        xlsx_files = [f for f in self.input_dir.glob("*.xlsx") if not f.name.startswith('~$')]
        
        self.logger.info(f"找到 {len(xlsx_files)} 个RG文件")
        for file in xlsx_files:
            self.logger.info(f"  - {file.name}")
            
        return xlsx_files
    
    def locate_rg_header(self, df):
        """定位RG标识的位置 - 在第2行中动态寻找RG列"""
        target_row = 1  # 第2行（0-based索引）
        
        # 在第2行中寻找"RG"标识
        if target_row < len(df):
            for j in range(len(df.columns)):
                cell_value = str(df.iloc[target_row, j]).strip()
                if cell_value.upper() == "RG":  # 不区分大小写
                    return (target_row, j)  # 返回0-based索引
        
        # 容错：如果第2行没找到，在前5行中寻找
        for i in range(min(5, len(df))):
            for j in range(len(df.columns)):
                cell_value = str(df.iloc[i, j]).strip()
                if cell_value.upper() == "RG":
                    return (i, j)
        
        return None
    
    def locate_r_unit(self, df, rg_col):
        """基于RG列位置定位R单位标识 - 在unit行（第7行）与RG列交叉位置查找"""
        unit_row = 6  # 第7行（0-based索引）
        
        # 首先在第7行与RG列交叉位置查找
        if unit_row < len(df) and rg_col < len(df.columns):
            cell_value = str(df.iloc[unit_row, rg_col]).strip()
            # 匹配包含数值+空格+R的格式，或包含"R"的内容
            if re.search(r'\bR\b', cell_value) or re.match(r'^\d+\.\d+\s+R$', cell_value):
                return (unit_row, rg_col)
        
        # 容错：在RG列的前10行中查找包含R单位的内容
        for i in range(min(10, len(df))):
            cell_value = str(df.iloc[i, rg_col]).strip()
            if re.match(r'^\d+\.\d+\s+R$', cell_value):
                return (i, rg_col)
        
        return None
    
    def extract_lot_id(self, filename):
        """
        从文件名中提取批次信息
        
        Args:
            filename: 文件名
            
        Returns:
            str: 批次字符串（使用正则表达式提取FA4Z-2484这样的模式）
        """
        # 使用正则表达式提取形如FA4Z-2484的模式（4个字母数字 + 短横线 + 4个数字）
        pattern = r'[A-Z0-9]{4}-[0-9]{4}'
        match = re.search(pattern, filename)
        
        if match:
            lot_id = match.group()
            self.logger.debug(f"提取批次信息: {filename} -> {lot_id}")
            return lot_id
        else:
            # 如果正则匹配失败，回退到使用完整文件名
            lot_id = Path(filename).stem
            self.logger.warning(f"正则匹配失败，使用完整文件名: {filename} -> {lot_id}")
            return lot_id
    
    def extract_rg_data(self, file_path):
        """从单个xlsx文件中提取RG数据"""
        self.logger.info(f"处理文件: {file_path.name}")
        
        try:
            # 读取Excel文件 - 优先使用calamine，不支持时自动回退openpyxl
            df = read_excel_fast(file_path, header=None)
            
            # 1. 定位RG标识
            rg_pos = self.locate_rg_header(df)
            if not rg_pos:
                self.logger.warning(f"文件 {file_path.name} 中未找到RG标识")
                return pd.DataFrame()
            
            rg_row, rg_col = rg_pos
            self.logger.info(f"  RG标识位置: 第{rg_row+1}行, 第{rg_col+1}列")
            
            # 2. 验证R单位
            r_unit_pos = self.locate_r_unit(df, rg_col)
            if r_unit_pos:
                r_row, r_col = r_unit_pos
                self.logger.info(f"  R单位位置: 第{r_row+1}行, 第{r_col+1}列")
            
            # 3. 找到数据起始行（Test No.行）
            test_no_row = None
            for i in range(len(df)):
                for j in range(len(df.columns)):
                    cell_value = str(df.iloc[i, j]).strip()
                    if "Test No" in cell_value:
                        test_no_row = i
                        break
                if test_no_row is not None:
                    break
            
            if test_no_row is None:
                self.logger.warning(f"文件 {file_path.name} 中未找到Test No.行")
                return pd.DataFrame()
            
            self.logger.info(f"  数据起始行: 第{test_no_row+2}行")
            
            # 4. 提取RG数据
            rg_values = []
            data_start_row = test_no_row + 1
            
            for i in range(data_start_row, len(df)):
                value = df.iloc[i, rg_col]
                if pd.notna(value) and isinstance(value, (int, float)):
                    rg_values.append(value)
                elif pd.notna(value):
                    # 尝试转换字符串为数值
                    try:
                        numeric_value = float(str(value).strip())
                        rg_values.append(numeric_value)
                    except ValueError:
                        continue  # 跳过非数值数据
            
            self.logger.info(f"  提取到 {len(rg_values)} 个RG数据点")
            
            # 5. 生成lot_ID
            lot_id = self.extract_lot_id(file_path.name)
            
            # 6. 创建结果DataFrame
            if rg_values:
                result_df = pd.DataFrame({
                    'lot_ID': [lot_id] * len(rg_values),
                    'RG(R)': rg_values
                })
                return result_df
            else:
                self.logger.warning(f"文件 {file_path.name} 中未提取到有效的RG数据")
                return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"处理文件 {file_path.name} 时出错: {e}")
            return pd.DataFrame()
    
    def merge_all_rg_data(self, file_list):
        """合并所有文件的RG数据"""
        self.logger.info("开始合并所有RG数据")
        
        all_data = []
        
        for file_path in file_list:
            file_data = self.extract_rg_data(file_path)
            if not file_data.empty:
                all_data.append(file_data)
        
        if all_data:
            # 合并所有数据
            merged_df = pd.concat(all_data, ignore_index=True)
            self.logger.info(f"合并完成，总共 {len(merged_df)} 条RG数据")
            return merged_df
        else:
            self.logger.warning("没有有效的RG数据可合并")
            return pd.DataFrame()
    
    def clean_and_format_rg(self, df):
        """清洗和格式化RG数据"""
        self.logger.info("开始清洗和格式化RG数据")
        
        if df.empty:
            return df
        
        # 1. 生成连续的NUM编号
        df['NUM'] = range(1, len(df) + 1)
        
        # 2. 重新排列列顺序
        df = df[['NUM', 'lot_ID', 'RG(R)']]
        
        # 3. 数据清洗
        original_count = len(df)
        
        # 过滤掉异常的RG值（如负数、过大的值等）
        df = df[df['RG(R)'] > 0]  # RG阻值应该大于0
        df = df[df['RG(R)'] < 1000]  # 过滤掉异常大的值
        
        # 重新生成NUM编号
        df = df.reset_index(drop=True)
        df['NUM'] = range(1, len(df) + 1)
        
        cleaned_count = len(df)
        if original_count != cleaned_count:
            self.logger.info(f"数据清洗完成，从 {original_count} 条数据清洗到 {cleaned_count} 条")
        
        return df
    
    def save_rg_result(self, df):
        """保存RG结果到Excel文件"""
        if df.empty:
            self.logger.warning("没有数据需要保存")
            return None
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 提取lot_ids用于生成文件名
        lot_ids = df['lot_ID'].tolist() if 'lot_ID' in df.columns else ['unknown']
        
        # 使用lot_id生成文件名
        filename = generate_lot_based_filename(lot_ids, "RG")
        output_file = self.output_dir / filename
        
        # 保存到Excel文件；超过Excel单sheet行数上限时会自动拆分为多个工作表
        if not write_excel_fast(df, output_file, index=False, engine='xlsxwriter', sheet_name='RG_Data'):
            self.logger.error(f"RG数据保存失败: {output_file}")
            return None
        
        self.logger.info(f"RG数据已保存到: {output_file}")
        self.logger.info(f"文件包含 {len(df)} 条RG数据")
        
        return output_file
    
    def run(self):
        """运行RG数据清洗流程"""
        self.logger.info("开始RG数据清洗流程")
        
        try:
            # 1. 扫描RG文件
            xlsx_files = self.scan_rg_files()
            if not xlsx_files:
                self.logger.warning("未找到RG文件，清洗流程结束")
                return None
            
            # 2. 合并所有RG数据
            merged_data = self.merge_all_rg_data(xlsx_files)
            if merged_data.empty:
                self.logger.warning("未提取到有效的RG数据，清洗流程结束")
                return None
            
            # 3. 清洗和格式化数据
            cleaned_data = self.clean_and_format_rg(merged_data)
            
            # 4. 保存结果
            output_file = self.save_rg_result(cleaned_data)
            
            self.logger.info("RG数据清洗流程完成")
            return output_file
            
        except Exception as e:
            self.logger.error(f"RG数据清洗流程出错: {e}")
            import traceback
            traceback.print_exc()
            return None

def main():
    """主函数"""
    print("=" * 60)
    print("RG数据清洗程序")
    print("=" * 60)
    
    # 创建RG清洗器
    cleaner = RGCleaner()
    
    # 运行清洗流程
    result = cleaner.run()
    
    if result:
        print(f"\n✅ RG数据清洗完成！")
        print(f"输出文件: {result}")
    else:
        print("\n❌ RG数据清洗失败，请检查日志信息")

if __name__ == "__main__":
    main() 
