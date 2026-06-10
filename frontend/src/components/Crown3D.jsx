// Photoreal 3D crown rendered with Three.js: procedural geometry (flared band +
// rims + spikes + gems), physically-based gold metal lit by a studio
// environment (RoomEnvironment -- no external HDR asset), spinning a full 360deg.
// Rendered to a small transparent canvas behind the GOAT card content.
import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'

const W = 132
const H = 120

export default function Crown3D() {
  const mountRef = useRef(null)
  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    renderer.setSize(W, H)
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.15
    mount.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(32, W / H, 0.1, 100)
    camera.position.set(0, 0.5, 4.3)
    camera.lookAt(0, 0.05, 0)

    // Studio reflections so the gold reads as real metal (no asset files).
    const pmrem = new THREE.PMREMGenerator(renderer)
    const envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture
    scene.environment = envTex

    const gold = new THREE.MeshStandardMaterial({
      color: 0xffcf47, metalness: 1.0, roughness: 0.24, envMapIntensity: 1.3,
    })
    const crown = new THREE.Group()

    const band = new THREE.Mesh(new THREE.CylinderGeometry(1.0, 0.9, 0.82, 80, 1, true), gold)
    crown.add(band)
    const rimBot = new THREE.Mesh(new THREE.TorusGeometry(0.93, 0.07, 20, 80), gold)
    rimBot.rotation.x = Math.PI / 2; rimBot.position.y = -0.41; crown.add(rimBot)
    const rimTop = new THREE.Mesh(new THREE.TorusGeometry(1.0, 0.055, 20, 80), gold)
    rimTop.rotation.x = Math.PI / 2; rimTop.position.y = 0.41; crown.add(rimTop)

    const gemColors = [0xff4d63, 0x4dc6ff, 0x6bff86, 0xffd84d]
    const N = 8
    const gems = []
    for (let i = 0; i < N; i++) {
      const a = (i / N) * Math.PI * 2
      const cx = Math.cos(a), cz = Math.sin(a)
      const spike = new THREE.Mesh(new THREE.ConeGeometry(0.17, 0.6, 28), gold)
      spike.position.set(cx * 0.97, 0.72, cz * 0.97)
      crown.add(spike)
      const c = gemColors[i % gemColors.length]
      const gemMat = new THREE.MeshStandardMaterial({
        color: c, metalness: 0.15, roughness: 0.12, envMapIntensity: 1.5,
        emissive: c, emissiveIntensity: 0.22,
      })
      const gem = new THREE.Mesh(new THREE.IcosahedronGeometry(0.11, 0), gemMat)
      gem.position.set(cx * 1.0, 0.12, cz * 1.0)
      crown.add(gem); gems.push(gemMat)
    }
    crown.rotation.x = 0.1   // slight downward tilt -> seen from just above
    scene.add(crown)

    scene.add(new THREE.AmbientLight(0xffffff, 0.2))
    const key = new THREE.DirectionalLight(0xfff2c8, 1.1)
    key.position.set(2.5, 3, 2.5); scene.add(key)

    let raf
    if (reduce) {
      crown.rotation.y = -0.5
      renderer.render(scene, camera)   // static frame, honors reduced-motion
    } else {
      const animate = () => {
        crown.rotation.y += 0.011
        renderer.render(scene, camera)
        raf = requestAnimationFrame(animate)
      }
      animate()
    }

    return () => {
      if (raf) cancelAnimationFrame(raf)
      envTex.dispose(); pmrem.dispose()
      scene.traverse((o) => {
        if (o.geometry) o.geometry.dispose()
        if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => m.dispose())
      })
      renderer.dispose()
      const gl = renderer.getContext()
      const lose = gl && gl.getExtension('WEBGL_lose_context')
      if (lose) lose.loseContext()
      if (renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement)
    }
  }, [])
  return <div className="crown3d" ref={mountRef} aria-hidden="true" />
}
