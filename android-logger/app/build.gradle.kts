plugins {
    id("com.android.application")
}

android {
    namespace = "jp.ecorun.logger"
    compileSdk = 36

    defaultConfig {
        applicationId = "jp.ecorun.logger"
        // Android 10+: foreground service type "location" and MediaStore Downloads.
        minSdk = 29
        targetSdk = 36
        versionCode = 1
        versionName = "0.1"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // Sideloaded to team phones only; the debug key is enough.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    // QR reading of the Ver.2 reference lines through Google Play services (no camera permission).
    implementation("com.google.android.gms:play-services-code-scanner:16.1.0")
    testImplementation("junit:junit:4.13.2")
}
