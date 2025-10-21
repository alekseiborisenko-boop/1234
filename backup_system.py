# -*- coding: utf-8 -*-
"""
Backup System with Git
Система резервного копирования с Git-версионированием
"""
import git
import os
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class BackupSystem:
    """Умная система бэкапов на Git"""
    
    def __init__(self, repo_path="/app"):
        self.repo_path = Path(repo_path)
        self.repo = None
        self.backup_metadata_file = self.repo_path / ".backup_metadata.json"
        self.init_git()
    
    def init_git(self):
        """Инициализация Git репозитория с .gitignore"""
        try:
            if not (self.repo_path / ".git").exists():
                logger.info("📦 Initializing Git repository...")
                self.repo = git.Repo.init(self.repo_path)
                
                # ✅ FIX: Configure git to trust this directory
                with self.repo.config_writer() as git_config:
                    git_config.set_value("safe", "directory", str(self.repo_path))
                    git_config.set_value("user", "name", "II-Agent Backup System")
                    git_config.set_value("user", "email", "backup@ii-agent.local")
                
                # Создаём .gitignore
                gitignore_content = """
# Python
__pycache__/
*.py[cod]
*.so
.Python

# Logs
logs/
*.log

# Docker
.dockerignore

# Temp files
*.tmp
*.bak
.DS_Store
"""
                gitignore_path = self.repo_path / ".gitignore"
                gitignore_path.write_text(gitignore_content.strip())
                
                # Первый коммит
                self.repo.index.add([".gitignore"])
                self.repo.index.commit("🎉 Initial commit - Backup system initialized")
                
                logger.info("✅ Git repository initialized")
            else:
                self.repo = git.Repo(self.repo_path)
                
                # ✅ FIX: Ensure existing repo is trusted
                with self.repo.config_writer() as git_config:
                    git_config.set_value("safe", "directory", str(self.repo_path))
                
                logger.info("✅ Git repository loaded")
                
        except Exception as e:
            logger.error(f"❌ Git init error: {e}")
            logger.warning("⚠️ Backup system will run without Git versioning")
            self.repo = None

    
    def create_backup(
        self, 
        message: str = "Auto backup",
        author: str = "II-Agent",
        tags: List[str] = None,
        critical: bool = False
    ) -> Dict[str, Any]:
        """
        Создание бэкапа с метаданными
        
        Args:
            message: Описание изменений
            author: Кто создал бэкап
            tags: Теги для категоризации
            critical: Критичный бэкап (не удалять автоматически)
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Проверяем есть ли изменения
            if not self.repo.is_dirty(untracked_files=True):
                logger.info("ℹ️  No changes to backup")
                return {
                    "success": True,
                    "message": "No changes detected",
                    "skipped": True
                }
            
            # Получаем список изменённых файлов
            changed_files = [item.a_path for item in self.repo.index.diff(None)]
            untracked_files = self.repo.untracked_files
            
            # Добавляем все изменения
            self.repo.git.add(A=True)
            
            # Создаём коммит
            commit_message = f"{message} [{timestamp}]\n\nAuthor: {author}"
            if tags:
                commit_message += f"\nTags: {', '.join(tags)}"
            
            commit = self.repo.index.commit(commit_message)
            
            # Создаём тег
            tag_name = f"backup_{timestamp}"
            if critical:
                tag_name = f"critical_{timestamp}"
            
            self.repo.create_tag(tag_name, message=message)
            
            # Сохраняем метаданные
            metadata = {
                "timestamp": timestamp,
                "commit": str(commit),
                "tag": tag_name,
                "message": message,
                "author": author,
                "tags": tags or [],
                "critical": critical,
                "changed_files": changed_files,
                "untracked_files": untracked_files,
                "date": datetime.now().isoformat()
            }
            
            self._save_metadata(metadata)
            
            logger.info(f"✅ Backup created: {tag_name}")
            logger.info(f"   Changed files: {len(changed_files)}")
            logger.info(f"   New files: {len(untracked_files)}")
            
            return {
                "success": True,
                "commit": str(commit),
                "tag": tag_name,
                "timestamp": timestamp,
                "changed_files": len(changed_files) + len(untracked_files),
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"❌ Backup creation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def rollback(
        self, 
        tag_name: Optional[str] = None,
        confirm: bool = False
    ) -> Dict[str, Any]:
        """
        Откат к бэкапу с подтверждением
        
        Args:
            tag_name: Имя тега для отката (None = предыдущий коммит)
            confirm: Подтверждение отката (защита от случайного отката)
        """
        try:
            if not confirm:
                return {
                    "success": False,
                    "error": "Rollback requires confirmation",
                    "message": "Set confirm=True to proceed"
                }
            
            # Создаём бэкап текущего состояния перед откатом
            pre_rollback = self.create_backup(
                message="Pre-rollback backup",
                critical=True
            )
            
            if tag_name:
                # Откат к конкретному тегу
                logger.warning(f"🔙 Rolling back to tag: {tag_name}")
                self.repo.git.checkout(tag_name, force=True)
                target = tag_name
            else:
                # Откат к предыдущему коммиту
                logger.warning("🔙 Rolling back to previous commit")
                self.repo.git.reset('--hard', 'HEAD~1')
                target = "HEAD~1"
            
            logger.info(f"✅ Rolled back to: {target}")
            
            return {
                "success": True,
                "rolled_back_to": target,
                "pre_rollback_backup": pre_rollback.get('tag')
            }
            
        except Exception as e:
            logger.error(f"❌ Rollback failed: {e}")
            return {"success": False, "error": str(e)}
    
    def list_backups(
        self, 
        limit: int = 10,
        include_critical_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Список бэкапов с фильтрацией"""
        try:
            tags = sorted(
                self.repo.tags, 
                key=lambda t: t.commit.committed_datetime, 
                reverse=True
            )
            
            backups = []
            for tag in tags:
                # Фильтр по критичным
                if include_critical_only and not tag.name.startswith('critical_'):
                    continue
                
                backup_info = {
                    "tag": tag.name,
                    "date": tag.commit.committed_datetime.isoformat(),
                    "message": tag.commit.message.split('\n')[0],
                    "commit": str(tag.commit),
                    "critical": tag.name.startswith('critical_')
                }
                
                backups.append(backup_info)
                
                if len(backups) >= limit:
                    break
            
            return backups
            
        except Exception as e:
            logger.error(f"❌ Error listing backups: {e}")
            return []
    
    def get_diff(
        self, 
        tag_name: str,
        current: bool = True
    ) -> Dict[str, Any]:
        """Просмотр изменений между бэкапом и текущим состоянием"""
        try:
            if current:
                # Diff с текущим состоянием
                diff = self.repo.git.diff(tag_name)
            else:
                # Diff с предыдущим коммитом
                diff = self.repo.git.diff(f"{tag_name}~1", tag_name)
            
            # Статистика
            stats = self.repo.git.diff(tag_name, '--stat')
            
            return {
                "success": True,
                "diff": diff,
                "stats": stats,
                "tag": tag_name
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting diff: {e}")
            return {"success": False, "error": str(e)}
    
    def cleanup_old_backups(
        self, 
        days: int = 30,
        keep_critical: bool = True,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """Очистка старых бэкапов"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            deleted = []
            kept = []
            
            for tag in self.repo.tags:
                tag_date = tag.commit.committed_datetime.replace(tzinfo=None)
                is_critical = tag.name.startswith('critical_')
                
                # Проверяем условия удаления
                should_delete = (
                    tag_date < cutoff_date and
                    not (is_critical and keep_critical)
                )
                
                if should_delete:
                    if not dry_run:
                        self.repo.delete_tag(tag)
                        logger.info(f"🗑️  Deleted old backup: {tag.name}")
                    deleted.append(tag.name)
                else:
                    kept.append(tag.name)
            
            return {
                "success": True,
                "deleted": len(deleted),
                "kept": len(kept),
                "deleted_tags": deleted if dry_run else deleted,
                "dry_run": dry_run
            }
            
        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")
            return {"success": False, "error": str(e)}
    
    def restore_file(
        self, 
        filepath: str,
        tag_name: str
    ) -> Dict[str, Any]:
        """Восстановление конкретного файла из бэкапа"""
        try:
            # Восстанавливаем файл из конкретного коммита
            self.repo.git.checkout(tag_name, '--', filepath)
            
            logger.info(f"✅ File restored: {filepath} from {tag_name}")
            
            return {
                "success": True,
                "file": filepath,
                "from_backup": tag_name
            }
            
        except Exception as e:
            logger.error(f"❌ File restore failed: {e}")
            return {"success": False, "error": str(e)}
    
    def get_backup_info(self, tag_name: str) -> Dict[str, Any]:
        """Полная информация о бэкапе"""
        try:
            tag = self.repo.tags[tag_name]
            commit = tag.commit
            
            # Получаем изменённые файлы
            if commit.parents:
                diff = commit.parents[0].diff(commit)
                changed_files = [item.a_path for item in diff]
            else:
                changed_files = []
            
            return {
                "success": True,
                "tag": tag_name,
                "commit": str(commit),
                "author": commit.author.name,
                "date": commit.committed_datetime.isoformat(),
                "message": commit.message,
                "changed_files": changed_files,
                "file_count": len(changed_files)
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting backup info: {e}")
            return {"success": False, "error": str(e)}
    
    def _save_metadata(self, metadata: Dict[str, Any]):
        """Сохранение метаданных бэкапа"""
        try:
            import json
            
            # Читаем существующие метаданные
            if self.backup_metadata_file.exists():
                with open(self.backup_metadata_file, 'r') as f:
                    all_metadata = json.load(f)
            else:
                all_metadata = []
            
            # Добавляем новые
            all_metadata.append(metadata)
            
            # Сохраняем
            with open(self.backup_metadata_file, 'w') as f:
                json.dump(all_metadata, f, indent=2)
                
        except Exception as e:
            logger.warning(f"⚠️  Could not save metadata: {e}")


# Глобальный экземпляр
backup_system = BackupSystem()
