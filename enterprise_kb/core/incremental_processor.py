"""增量文档处理模块，避免重新处理整个文档"""
import os
import logging
import hashlib
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Set, Tuple, Union
from pathlib import Path

from llama_index.core import Document
from llama_index.core.schema import BaseNode, TextNode

from enterprise_kb.core.config.settings import settings
from enterprise_kb.storage.vector_store_manager import get_vector_store_manager

logger = logging.getLogger(__name__)

class DocumentState:
    """文档状态，用于跟踪文档变化"""
    
    def __init__(
        self,
        doc_id: str,
        file_path: str,
        file_hash: str,
        chunk_hashes: List[str],
        metadata: Dict[str, Any],
        last_processed: float,
        node_ids: List[str]
    ):
        """初始化文档状态
        
        Args:
            doc_id: 文档ID
            file_path: 文件路径
            file_hash: 文件哈希
            chunk_hashes: 块哈希列表
            metadata: 文档元数据
            last_processed: 上次处理时间戳
            node_ids: 节点ID列表
        """
        self.doc_id = doc_id
        self.file_path = file_path
        self.file_hash = file_hash
        self.chunk_hashes = chunk_hashes
        self.metadata = metadata
        self.last_processed = last_processed
        self.node_ids = node_ids
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentState':
        """从字典创建文档状态
        
        Args:
            data: 字典数据
            
        Returns:
            文档状态实例
        """
        return cls(
            doc_id=data["doc_id"],
            file_path=data["file_path"],
            file_hash=data["file_hash"],
            chunk_hashes=data["chunk_hashes"],
            metadata=data["metadata"],
            last_processed=data["last_processed"],
            node_ids=data["node_ids"]
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典
        
        Returns:
            字典表示
        """
        return {
            "doc_id": self.doc_id,
            "file_path": self.file_path,
            "file_hash": self.file_hash,
            "chunk_hashes": self.chunk_hashes,
            "metadata": self.metadata,
            "last_processed": self.last_processed,
            "node_ids": self.node_ids
        }

class IncrementalProcessor:
    """增量文档处理器，避免重新处理整个文档"""
    
    def __init__(self, state_dir: Optional[str] = None):
        """初始化增量处理器
        
        Args:
            state_dir: 状态文件目录，如果为None则使用默认目录
        """
        self.state_dir = state_dir or os.path.join(settings.PROCESSED_DIR, "states")
        os.makedirs(self.state_dir, exist_ok=True)
        
        # 获取向量存储管理器
        self.vector_store_manager = get_vector_store_manager()
        
        logger.info(f"初始化增量处理器，状态目录: {self.state_dir}")
    
    def _get_state_path(self, doc_id: str) -> str:
        """获取状态文件路径
        
        Args:
            doc_id: 文档ID
            
        Returns:
            状态文件路径
        """
        return os.path.join(self.state_dir, f"{doc_id}.json")
    
    def _compute_file_hash(self, file_path: str) -> str:
        """计算文件哈希
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件哈希
        """
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _compute_text_hash(self, text: str) -> str:
        """计算文本哈希
        
        Args:
            text: 文本
            
        Returns:
            文本哈希
        """
        return hashlib.md5(text.encode("utf-8")).hexdigest()
    
    def load_document_state(self, doc_id: str) -> Optional[DocumentState]:
        """加载文档状态
        
        Args:
            doc_id: 文档ID
            
        Returns:
            文档状态，如果不存在则返回None
        """
        state_path = self._get_state_path(doc_id)
        if not os.path.exists(state_path):
            return None
        
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return DocumentState.from_dict(data)
        except Exception as e:
            logger.error(f"加载文档状态失败: {str(e)}")
            return None
    
    def save_document_state(self, state: DocumentState) -> bool:
        """保存文档状态
        
        Args:
            state: 文档状态
            
        Returns:
            是否成功
        """
        state_path = self._get_state_path(state.doc_id)
        try:
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存文档状态失败: {str(e)}")
            return False
    
    def delete_document_state(self, doc_id: str) -> bool:
        """删除文档状态
        
        Args:
            doc_id: 文档ID
            
        Returns:
            是否成功
        """
        state_path = self._get_state_path(doc_id)
        if not os.path.exists(state_path):
            return True
        
        try:
            os.remove(state_path)
            return True
        except Exception as e:
            logger.error(f"删除文档状态失败: {str(e)}")
            return False
    
    async def check_document_changes(
        self,
        doc_id: str,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[DocumentState]]:
        """检查文档是否有变化
        
        Args:
            doc_id: 文档ID
            file_path: 文件路径
            metadata: 文档元数据
            
        Returns:
            (是否有变化, 文档状态)
        """
        # 加载文档状态
        state = self.load_document_state(doc_id)
        
        # 如果状态不存在，则认为文档有变化
        if state is None:
            return True, None
        
        # 如果文件路径不匹配，则认为文档有变化
        if state.file_path != file_path:
            return True, state
        
        # 计算文件哈希
        try:
            file_hash = self._compute_file_hash(file_path)
        except Exception as e:
            logger.error(f"计算文件哈希失败: {str(e)}")
            return True, state
        
        # 如果文件哈希不匹配，则认为文档有变化
        if state.file_hash != file_hash:
            return True, state
        
        # 如果元数据有变化，则认为文档有变化
        if metadata and metadata != state.metadata:
            return True, state
        
        # 文档没有变化
        return False, state
    
    async def process_document_incrementally(
        self,
        doc_id: str,
        file_path: str,
        chunks: List[str],
        metadata: Dict[str, Any],
        datasource_name: str,
        processor_func: callable
    ) -> Dict[str, Any]:
        """增量处理文档
        
        Args:
            doc_id: 文档ID
            file_path: 文件路径
            chunks: 文档块列表
            metadata: 文档元数据
            datasource_name: 数据源名称
            processor_func: 处理函数，接收块文本和元数据，返回节点列表
            
        Returns:
            处理结果
        """
        # 检查文档是否有变化
        has_changes, state = await self.check_document_changes(doc_id, file_path, metadata)
        
        # 计算文件哈希
        file_hash = self._compute_file_hash(file_path)
        
        # 计算块哈希
        chunk_hashes = [self._compute_text_hash(chunk) for chunk in chunks]
        
        # 如果文档没有变化，直接返回
        if not has_changes and state:
            logger.info(f"文档 {doc_id} 没有变化，跳过处理")
            return {
                "doc_id": doc_id,
                "file_name": os.path.basename(file_path),
                "metadata": metadata,
                "status": "unchanged",
                "node_count": len(state.node_ids),
                "datasource": datasource_name
            }
        
        # 如果是新文档，直接处理所有块
        if state is None:
            logger.info(f"新文档 {doc_id}，处理所有块")
            
            # 处理所有块
            all_nodes = []
            for i, chunk in enumerate(chunks):
                # 创建块元数据
                chunk_metadata = metadata.copy()
                chunk_metadata["chunk_index"] = i
                
                # 处理块
                nodes = processor_func(chunk, chunk_metadata)
                all_nodes.extend(nodes)
            
            # 添加节点到向量存储
            node_ids = await self.vector_store_manager.add_nodes(all_nodes, datasource_name)
            
            # 保存文档状态
            new_state = DocumentState(
                doc_id=doc_id,
                file_path=file_path,
                file_hash=file_hash,
                chunk_hashes=chunk_hashes,
                metadata=metadata,
                last_processed=time.time(),
                node_ids=node_ids
            )
            self.save_document_state(new_state)
            
            return {
                "doc_id": doc_id,
                "file_name": os.path.basename(file_path),
                "metadata": metadata,
                "status": "success",
                "node_count": len(node_ids),
                "text_chars": sum(len(chunk) for chunk in chunks),
                "datasource": datasource_name
            }
        
        # 如果文档有变化，增量处理
        logger.info(f"文档 {doc_id} 有变化，增量处理")
        
        # 比较块哈希，找出变化的块
        old_hashes = set(state.chunk_hashes)
        new_hashes = set(chunk_hashes)
        
        # 需要添加的块
        added_hashes = new_hashes - old_hashes
        added_indices = [i for i, h in enumerate(chunk_hashes) if h in added_hashes]
        
        # 需要删除的块
        removed_hashes = old_hashes - new_hashes
        removed_indices = [i for i, h in enumerate(state.chunk_hashes) if h in removed_hashes]
        
        # 未变化的块
        unchanged_hashes = old_hashes.intersection(new_hashes)
        unchanged_indices = [i for i, h in enumerate(chunk_hashes) if h in unchanged_hashes]
        
        logger.info(f"文档 {doc_id} 变化分析: 添加 {len(added_indices)} 块，删除 {len(removed_indices)} 块，未变化 {len(unchanged_indices)} 块")
        
        # 如果变化太大（超过50%），直接重新处理整个文档
        if len(added_indices) + len(removed_indices) > len(chunks) * 0.5:
            logger.info(f"文档 {doc_id} 变化过大，重新处理整个文档")
            
            # 删除旧节点
            await self.vector_store_manager.delete_nodes(doc_id, datasource_name)
            
            # 处理所有块
            all_nodes = []
            for i, chunk in enumerate(chunks):
                # 创建块元数据
                chunk_metadata = metadata.copy()
                chunk_metadata["chunk_index"] = i
                
                # 处理块
                nodes = processor_func(chunk, chunk_metadata)
                all_nodes.extend(nodes)
            
            # 添加节点到向量存储
            node_ids = await self.vector_store_manager.add_nodes(all_nodes, datasource_name)
            
            # 保存文档状态
            new_state = DocumentState(
                doc_id=doc_id,
                file_path=file_path,
                file_hash=file_hash,
                chunk_hashes=chunk_hashes,
                metadata=metadata,
                last_processed=time.time(),
                node_ids=node_ids
            )
            self.save_document_state(new_state)
            
            return {
                "doc_id": doc_id,
                "file_name": os.path.basename(file_path),
                "metadata": metadata,
                "status": "reprocessed",
                "node_count": len(node_ids),
                "text_chars": sum(len(chunk) for chunk in chunks),
                "datasource": datasource_name
            }
        
        # 增量处理
        # 1. 删除已移除的块
        if removed_indices:
            # 获取要删除的节点ID
            removed_node_ids = [state.node_ids[i] for i in removed_indices if i < len(state.node_ids)]
            
            # 删除节点
            for node_id in removed_node_ids:
                try:
                    await self.vector_store_manager.delete_nodes(node_id, datasource_name)
                except Exception as e:
                    logger.error(f"删除节点 {node_id} 失败: {str(e)}")
        
        # 2. 添加新块
        added_nodes = []
        for i in added_indices:
            # 创建块元数据
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_index"] = i
            
            # 处理块
            nodes = processor_func(chunks[i], chunk_metadata)
            added_nodes.extend(nodes)
        
        # 添加节点到向量存储
        added_node_ids = []
        if added_nodes:
            added_node_ids = await self.vector_store_manager.add_nodes(added_nodes, datasource_name)
        
        # 3. 更新文档状态
        # 构建新的节点ID列表
        new_node_ids = []
        old_node_map = {state.chunk_hashes[i]: state.node_ids[i] for i in range(len(state.chunk_hashes)) if i < len(state.node_ids)}
        
        added_node_index = 0
        for i, chunk_hash in enumerate(chunk_hashes):
            if chunk_hash in old_hashes:
                # 未变化的块，使用旧节点ID
                node_id = old_node_map.get(chunk_hash)
                if node_id:
                    new_node_ids.append(node_id)
            else:
                # 新增的块，使用新节点ID
                if added_node_index < len(added_node_ids):
                    new_node_ids.append(added_node_ids[added_node_index])
                    added_node_index += 1
        
        # 保存文档状态
        new_state = DocumentState(
            doc_id=doc_id,
            file_path=file_path,
            file_hash=file_hash,
            chunk_hashes=chunk_hashes,
            metadata=metadata,
            last_processed=time.time(),
            node_ids=new_node_ids
        )
        self.save_document_state(new_state)
        
        return {
            "doc_id": doc_id,
            "file_name": os.path.basename(file_path),
            "metadata": metadata,
            "status": "updated",
            "node_count": len(new_node_ids),
            "added_nodes": len(added_node_ids),
            "removed_nodes": len(removed_indices),
            "unchanged_nodes": len(unchanged_indices),
            "datasource": datasource_name
        }

# 创建单例实例
_incremental_processor = None

def get_incremental_processor() -> IncrementalProcessor:
    """获取增量处理器单例"""
    global _incremental_processor
    if _incremental_processor is None:
        _incremental_processor = IncrementalProcessor()
    return _incremental_processor
