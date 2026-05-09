# D-23-09 / Phase 21: 精简 keep 策略 — 移除库自带的冗余规则，只保留应用特有逻辑

-keepattributes *Annotation*, InnerClasses, Signature

# ===== DTO 层 =====
# kotlinx.serialization 通过 @Serializable 反射访问字段，保留 DTO 字段
-keepclasseswithmembers class **.data.remote.dto.** {
    <fields>;
}

# ===== API 接口 =====
# Retrofit 需要保留接口类名和方法签名以便运行时生成代理
-keep,allowobfuscation interface **.data.remote.api.** {
    *** *(...);
}
-keepclassmembers,allowobfuscation interface **.data.remote.api.** {
    *** *(...);
}

# ===== SceneBubble 密封类 — @SerialName 多态序列化需要类名匹配 =====
-keep class com.drama.app.domain.model.SceneBubble { *; }
-keep class com.drama.app.domain.model.SceneBubble$* { *; }
-keep class com.drama.app.domain.model.InteractionType { *; }

# ===== Application 类 =====
-keep class com.drama.app.DramaApplication { *; }

# ===== Hilt / Dagger =====
# Hilt 生成的代码及内部类在运行时通过反射访问，需保留
-keep class dagger.hilt.** { *; }
-keep class javax.inject.** { *; }
-keep class * extends dagger.hilt.android.internal.managers.ViewComponentManager$FragmentContextWrapper { *; }

# ===== kotlinx.serialization =====
# 内部类在序列化/反序列化时通过反射访问
-keep class kotlinx.serialization.** { *; }
-keepclassmembers class kotlinx.serialization.** {
    *** Companion;
}

# ===== OkHttp / Retrofit 警告抑制 =====
-dontwarn okhttp3.**
-dontwarn okio.**
-dontwarn retrofit2.**
-dontwarn androidx.compose.**

# ===== Tink / security-crypto (D-04) =====
# error_prone_annotations 是 Tink 的可选依赖，R8 缺少类检测报错
-dontwarn com.google.errorprone.annotations.CanIgnoreReturnValue
-dontwarn com.google.errorprone.annotations.CheckReturnValue
-dontwarn com.google.errorprone.annotations.Immutable
-dontwarn com.google.errorprone.annotations.RestrictedApi

# ===== WebView / JS Bridge (if any) =====
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
