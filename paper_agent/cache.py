"""
缓存管理系统
"""
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

import config


class CacheManager:
    """缓存管理器"""
    
    def __init__(self, cache_dir: Path = None):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录路径
        """
        self.cache_dir = cache_dir or config.CACHE_DIR
        self.cache_dir.mkdir(exist_ok=True)
        
        # 元数据文件
        self.metadata_file = self.cache_dir / "metadata.json"
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """加载元数据"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_metadata(self):
        """保存元数据"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存元数据失败: {e}")
    
    def _get_cache_key(self, query: str) -> str:
        """生成缓存键"""
        # 使用 MD5 哈希作为文件名
        return hashlib.md5(query.lower().encode('utf-8')).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{cache_key}.json"
    
    def get(self, query: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存的查询结果
        
        Args:
            query: 查询字符串（论文标题）
            
        Returns:
            缓存的结果，如果不存在或过期则返回 None
        """
        cache_key = self._get_cache_key(query)
        cache_path = self._get_cache_path(cache_key)
        
        # 检查缓存是否存在
        if not cache_path.exists():
            return None
        
        # 检查是否过期
        metadata = self.metadata.get(cache_key, {})
        cached_time_str = metadata.get('cached_at')
        
        if cached_time_str:
            try:
                cached_time = datetime.fromisoformat(cached_time_str)
                expiry_time = cached_time + timedelta(days=config.CACHE_EXPIRY_DAYS)
                
                if datetime.now() > expiry_time:
                    # 缓存已过期
                    self.delete(query)
                    return None
            except Exception:
                pass
        
        # 读取缓存
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"读取缓存失败: {e}")
            return None
    
    def set(self, query: str, data: Dict[str, Any]):
        """
        保存查询结果到缓存
        
        Args:
            query: 查询字符串（论文标题）
            data: 要缓存的数据
        """
        cache_key = self._get_cache_key(query)
        cache_path = self._get_cache_path(cache_key)
        
        try:
            # 保存数据
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 更新元数据
            self.metadata[cache_key] = {
                'query': query,
                'cached_at': datetime.now().isoformat(),
            }
            self._save_metadata()
            
        except Exception as e:
            print(f"保存缓存失败: {e}")
    
    def delete(self, query: str):
        """
        删除缓存
        
        Args:
            query: 查询字符串（论文标题）
        """
        cache_key = self._get_cache_key(query)
        cache_path = self._get_cache_path(cache_key)
        
        # 删除缓存文件
        if cache_path.exists():
            cache_path.unlink()
        
        # 删除元数据
        if cache_key in self.metadata:
            del self.metadata[cache_key]
            self._save_metadata()
    
    def clear_all(self):
        """清空所有缓存"""
        for cache_file in self.cache_dir.glob("*.json"):
            if cache_file != self.metadata_file:
                cache_file.unlink()
        
        self.metadata = {}
        self._save_metadata()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        cache_files = list(self.cache_dir.glob("*.json"))
        cache_files = [f for f in cache_files if f != self.metadata_file]
        
        total_size = sum(f.stat().st_size for f in cache_files)
        
        return {
            'total_entries': len(cache_files),
            'total_size_mb': total_size / (1024 * 1024),
            'cache_dir': str(self.cache_dir),
        }

