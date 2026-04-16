package com.drama.app.di

import com.drama.app.data.repository.DramaRepositoryImpl
import com.drama.app.domain.repository.DramaRepository
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class DramaModule {
    @Binds
    @Singleton
    abstract fun bindDramaRepository(impl: DramaRepositoryImpl): DramaRepository
}
