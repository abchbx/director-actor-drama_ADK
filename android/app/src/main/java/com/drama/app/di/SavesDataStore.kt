package com.drama.app.di

import javax.inject.Qualifier

/**
 * 限定符注解 — 标记用于戏剧存档的 DataStore 实例
 *
 * 与默认的 drama_settings DataStore 区分，
 * 避免两个 DataStore 注入时产生歧义。
 */
@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class SavesDataStore
