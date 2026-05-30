<template>
  <div class="layout">
    <el-container style="height:100vh">
      <el-aside :width="collapsed ? '64px' : '220px'" class="sidebar">
        <sidebar :collapsed="collapsed" @toggle="toggleCollapsed" />
      </el-aside>
      <el-container>
        <el-header class="header">
          <el-button icon="el-icon-s-unfold" @click="toggleCollapsed" circle></el-button>
          <div class="title">Vue Admin Custom</div>
        </el-header>
        <el-main class="main">
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script>
import Sidebar from './Sidebar.vue'
export default {
  components: { Sidebar },
  data() {
    return { collapsed: false }
  },
  methods: {
    toggleCollapsed() { this.collapsed = !this.collapsed }
  }
}
</script>

<style scoped>
.header{ display:flex; align-items:center; gap:12px; padding:8px 16px; background:#fff }
.title{ font-weight:600 }
.main{ padding:16px; background:#f5f7fa; height:calc(100vh - 64px); overflow:auto }
.sidebar{ background:var(--el-color-primary) }
</style>
