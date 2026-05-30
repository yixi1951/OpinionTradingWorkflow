<template>
  <div class="sidebar-inner">
    <div class="logo" :class="{collapsed}">OP Admin</div>
    <el-menu :collapse="collapsed" router default-active="/dashboard" class="el-menu-vertical-demo" :background-color="menuBg">
      <el-menu-item index="/dashboard">
        <i class="el-icon-s-home"></i>
        <span slot="title">Dashboard</span>
      </el-menu-item>
      <el-menu-item index="/bigdata">
        <i class="el-icon-data-analysis"></i>
        <span slot="title">BigData</span>
      </el-menu-item>
      <el-menu-item index="/freqtrade">
        <i class="el-icon-trend"></i>
        <span slot="title">Trading</span>
      </el-menu-item>
      <el-menu-item index="/streamlit">
        <i class="el-icon-document"></i>
        <span slot="title">Indicators</span>
      </el-menu-item>
      <el-menu-item index="/realtime">
        <i class="el-icon-bell"></i>
        <span slot="title">Realtime</span>
      </el-menu-item>
      <el-menu-item index="/brand">
        <i class="el-icon-star-off"></i>
        <span slot="title">Brand</span>
      </el-menu-item>
    </el-menu>
    <div class="collapse-btn">
      <el-button @click="$emit('toggle')" icon="el-icon-s-fold" circle size="small"></el-button>
    </div>
  </div>
</template>

<script>
export default {
  props: { collapsed: { type: Boolean, default: false } },
  computed: {
    menuBg() { return 'transparent' }
  }
}
</script>

<style scoped>
.sidebar-inner{ color:#fff; height:100%; display:flex; flex-direction:column }
.logo{ padding:20px; font-weight:700; color:#fff }
.collapse-btn{ margin-top:auto; padding:12px }
.el-menu-vertical-demo{ background:transparent; color:#fff }
</style>
