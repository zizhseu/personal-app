<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>设置</h1>
        <p class="sub">应用偏好，保存在本机浏览器中</p>
      </div>
    </div>

    <el-card shadow="never" class="block-card">
      <div class="group-title">导入</div>
      <div class="setting-row">
        <div class="setting-info">
          <div class="setting-name">导入时用文件名作为标签</div>
          <div class="setting-desc">
            导入 .md 文件时，自动把文件名（去掉扩展名）添加为该批题目的标签
          </div>
        </div>
        <el-switch v-model="importFilenameAsTag" />
      </div>

      <div class="group-title margin-top">笔试选择</div>
      <div class="setting-row">
        <div class="setting-info">
          <div class="setting-name">答案与解析显示时机</div>
          <div class="setting-desc">
            立即显示：打开题目即见答案；作答后显示：选择选项提交后显示并判定对错；手动查看：点击按钮后显示
          </div>
        </div>
        <el-radio-group v-model="quizAnswerMode" size="small">
          <el-radio-button value="instant">立即显示</el-radio-button>
          <el-radio-button value="afterAnswer">作答后</el-radio-button>
          <el-radio-button value="manual">手动查看</el-radio-button>
        </el-radio-group>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useSettingsStore } from '../store'

const store = useSettingsStore()

const importFilenameAsTag = computed({
  get: () => store.importFilenameAsTag,
  set: (v) => store.update({ importFilenameAsTag: v }),
})

const quizAnswerMode = computed({
  get: () => store.quizAnswerMode,
  set: (v) => store.update({ quizAnswerMode: v }),
})
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-width: 0;
}

.page-head h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--ink);
}

.sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--ink-3);
}

.block-card {
  border-radius: var(--radius-card);
}

.group-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-3);
  margin-bottom: 4px;
}

.group-title.margin-top {
  margin-top: 18px;
}

.setting-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 0;
}

.setting-info {
  flex: 1;
  min-width: 0;
}

.setting-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
}

.setting-desc {
  margin-top: 3px;
  font-size: 12.5px;
  color: var(--ink-3);
}
</style>
