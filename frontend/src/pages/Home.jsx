import React, { useState, useEffect, useRef } from 'react';
import { Box, Typography, Button, useTheme, alpha, Container, Grid, Skeleton } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Camera, ChartLine, Eye, ArrowRight, Play, Pulse, Detective, Scan, CircleNotch } from '@phosphor-icons/react';
import axios from 'axios';

const AnimatedNumber = ({ value, duration = 2000 }) => {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    let startTime;
    const animate = (timestamp) => {
      if (!startTime) startTime = timestamp;
      const progress = Math.min((timestamp - startTime) / duration, 1);
      setDisplayValue(Math.floor(progress * value));
      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };
    requestAnimationFrame(animate);
  }, [value, duration]);

  return <span>{displayValue.toLocaleString()}</span>;
};

// Computer Vision Animation Component
const VisionAnimation = () => {
  const canvasRef = useRef(null);
  const animationRef = useRef(null);
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;

    // Detection boxes with softer colors
    const detections = [
      { x: 0.2, y: 0.3, w: 0.15, h: 0.25, label: 'Person', confidence: 0.92, color: isDark ? '#06b6d4' : '#0891b2' },
      { x: 0.6, y: 0.4, w: 0.2, h: 0.3, label: 'Car', confidence: 0.87, color: isDark ? '#10b981' : '#059669' },
      { x: 0.1, y: 0.6, w: 0.12, h: 0.18, label: 'Bicycle', confidence: 0.79, color: isDark ? '#8b5cf6' : '#7c3aed' },
    ];

    let animationProgress = 0;
    let scanLineY = 0;
    let isAnimating = true;

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      // Update animation progress - even slower for one smooth cycle
      if (isAnimating) {
        animationProgress += 0.003;
        
        // Stop after one complete cycle
        if (animationProgress >= 1) {
          isAnimating = false;
          animationProgress = 1;
        }
      }
      
      // Draw scan line only during animation
      if (isAnimating) {
        scanLineY = (scanLineY + 1) % canvas.height;
        
        const gradient = ctx.createLinearGradient(0, scanLineY - 20, 0, scanLineY + 20);
        gradient.addColorStop(0, 'transparent');
        gradient.addColorStop(0.5, isDark ? 'rgba(6, 182, 212, 0.5)' : 'rgba(6, 182, 212, 0.8)');
        gradient.addColorStop(1, 'transparent');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, scanLineY - 20, canvas.width, 40);
      }
      
      detections.forEach((det, index) => {
        const delay = index * 0.3;
        const progress = Math.max(0, Math.min(1, (animationProgress - delay) * 2));
        
        if (progress > 0) {
          const x = det.x * canvas.width;
          const y = det.y * canvas.height;
          const w = det.w * canvas.width * progress;
          const h = det.h * canvas.height * progress;
          
          // Draw box with animated dash pattern
          ctx.strokeStyle = det.color;
          ctx.lineWidth = isDark ? 2 : 2.5;
          const dashOffset = (Date.now() / 50) % 20;
          ctx.setLineDash([8, 4]);
          ctx.lineDashOffset = -dashOffset;
          ctx.strokeRect(x, y, w, h);
          ctx.setLineDash([]);
          
          // Draw corners
          const cornerLength = 20;
          ctx.lineWidth = isDark ? 3 : 4;
          
          // Top-left
          ctx.beginPath();
          ctx.moveTo(x, y + cornerLength);
          ctx.lineTo(x, y);
          ctx.lineTo(x + cornerLength, y);
          ctx.stroke();
          
          // Top-right
          ctx.beginPath();
          ctx.moveTo(x + w - cornerLength, y);
          ctx.lineTo(x + w, y);
          ctx.lineTo(x + w, y + cornerLength);
          ctx.stroke();
          
          // Bottom-left
          ctx.beginPath();
          ctx.moveTo(x, y + h - cornerLength);
          ctx.lineTo(x, y + h);
          ctx.lineTo(x + cornerLength, y + h);
          ctx.stroke();
          
          // Bottom-right
          ctx.beginPath();
          ctx.moveTo(x + w - cornerLength, y + h);
          ctx.lineTo(x + w, y + h);
          ctx.lineTo(x + w, y + h - cornerLength);
          ctx.stroke();
          
          // Draw label with modern styling
          if (progress > 0.5) {
            // Modern font and sizing
            ctx.font = '600 13px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
            const text = `${det.label} ${Math.round(det.confidence * 100)}%`;
            const textMetrics = ctx.measureText(text);
            const textWidth = textMetrics.width + 20;
            const textHeight = 26;
            
            // Position label to the right of the detection box
            const labelX = x + w + 8;
            const labelY = y;
            
            // Draw modern label background
            ctx.fillStyle = isDark ? 'rgba(0, 0, 0, 0.7)' : 'rgba(255, 255, 255, 0.85)';
            ctx.shadowColor = 'rgba(0, 0, 0, 0.1)';
            ctx.shadowBlur = 8;
            ctx.shadowOffsetX = 0;
            ctx.shadowOffsetY = 2;
            
            // Rounded rectangle
            const radius = 6;
            ctx.beginPath();
            ctx.moveTo(labelX + radius, labelY);
            ctx.lineTo(labelX + textWidth - radius, labelY);
            ctx.quadraticCurveTo(labelX + textWidth, labelY, labelX + textWidth, labelY + radius);
            ctx.lineTo(labelX + textWidth, labelY + textHeight - radius);
            ctx.quadraticCurveTo(labelX + textWidth, labelY + textHeight, labelX + textWidth - radius, labelY + textHeight);
            ctx.lineTo(labelX + radius, labelY + textHeight);
            ctx.quadraticCurveTo(labelX, labelY + textHeight, labelX, labelY + textHeight - radius);
            ctx.lineTo(labelX, labelY + radius);
            ctx.quadraticCurveTo(labelX, labelY, labelX + radius, labelY);
            ctx.closePath();
            ctx.fill();
            
            // Reset shadow
            ctx.shadowColor = 'transparent';
            
            // Draw colored accent line
            ctx.fillStyle = det.color;
            ctx.fillRect(labelX, labelY, 3, textHeight);
            
            // Draw text with modern styling
            ctx.font = '600 13px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
            ctx.fillStyle = isDark ? det.color : det.color;
            ctx.fillText(text, labelX + 10, labelY + textHeight/2 + 4);
          }
        }
      });

      animationRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isDark]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: '100%',
        height: '100%',
        opacity: 0.6,
      }}
    />
  );
};

const Home = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const [stats, setStats] = useState({ detections: 0, cameras: 0, uptime: 99.9 });
  const [loading, setLoading] = useState(true);
  const [hoveredStat, setHoveredStat] = useState(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await axios.get('http://localhost:8000/api/detection-stats/real-time');
        setStats({
          detections: response.data.totalDetections || 0,
          cameras: response.data.activeCameras || 0,
          uptime: 99.9
        });
      } catch (error) {
        console.error('Error fetching stats:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  const isDark = theme.palette.mode === 'dark';

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Computer Vision Animation Background */}
      <Box
        sx={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          opacity: isDark ? 0.08 : 0.2,
          pointerEvents: 'none',
        }}
      >
        <VisionAnimation />
      </Box>

      {/* Animated Background Gradient */}
      <Box
        sx={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: isDark
            ? 'radial-gradient(circle at 20% 80%, rgba(6, 182, 212, 0.15) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(59, 130, 246, 0.15) 0%, transparent 50%), radial-gradient(circle at 40% 40%, rgba(139, 92, 246, 0.1) 0%, transparent 50%)'
            : 'radial-gradient(circle at 20% 80%, rgba(6, 182, 212, 0.12) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(59, 130, 246, 0.12) 0%, transparent 50%), radial-gradient(circle at 40% 40%, rgba(139, 92, 246, 0.08) 0%, transparent 50%)',
          animation: 'pulse 30s ease-in-out infinite',
          '@keyframes pulse': {
            '0%, 100%': { 
              transform: 'scale(1)',
              opacity: 0.9,
            },
            '50%': { 
              transform: 'scale(1.02)',
              opacity: 0.95,
            },
          },
        }}
      />

      {/* Hero Section */}
      <Container maxWidth="xl" sx={{ pt: 10, pb: 6, position: 'relative', zIndex: 1 }}>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
        >
          <Box sx={{ textAlign: 'center', mb: 8 }}>
            <Box sx={{ position: 'relative', display: 'inline-block', mb: 3 }}>
              <motion.div
                animate={{ rotate: [0, 360] }}
                transition={{ duration: 3, ease: "easeOut" }}
                style={{ position: 'absolute', top: -40, right: -40 }}
              >
                <Scan size={80} color={alpha(theme.palette.primary.main, 0.2)} weight="thin" />
              </motion.div>
              <Typography
                variant="h1"
                sx={{
                  fontSize: { xs: '2.5rem', md: '4rem', lg: '5rem' },
                  fontWeight: 900,
                  background: isDark
                    ? 'linear-gradient(135deg, #06b6d4 0%, #3b82f6 50%, #8b5cf6 100%)'
                    : 'linear-gradient(135deg, #0891b2 0%, #2563eb 50%, #7c3aed 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundSize: '200% 200%',
                  animation: 'gradient-shift 5s ease infinite',
                  '@keyframes gradient-shift': {
                    '0%': { backgroundPosition: '0% 50%' },
                    '50%': { backgroundPosition: '100% 50%' },
                    '100%': { backgroundPosition: '0% 50%' },
                  },
                }}
              >
                Vision Detection System
              </Typography>
            </Box>
            <Typography
              variant="h5"
              sx={{
                color: isDark ? alpha(theme.palette.common.white, 0.7) : alpha(theme.palette.common.black, 0.7),
                mb: 5,
                maxWidth: '600px',
                mx: 'auto',
                fontWeight: 400,
                lineHeight: 1.6,
              }}
            >
              Real-time object detection powered by advanced AI
            </Typography>

            {/* Action Buttons */}
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', flexWrap: 'wrap' }}>
              <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                <Button
                  variant="contained"
                  size="large"
                  onClick={() => navigate('/dashboard')}
                  endIcon={<ArrowRight weight="bold" />}
                  sx={{
                    px: 4,
                    py: 1.75,
                    borderRadius: 3,
                    fontSize: '1rem',
                    fontWeight: 600,
                    background: isDark
                      ? 'linear-gradient(135deg, #06b6d4 0%, #0891b2 100%)'
                      : 'linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%)',
                    boxShadow: isDark
                      ? '0 8px 32px rgba(6, 182, 212, 0.4)'
                      : '0 8px 32px rgba(14, 165, 233, 0.3)',
                    '&:hover': {
                      background: isDark
                        ? 'linear-gradient(135deg, #0891b2 0%, #0e7490 100%)'
                        : 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
                      boxShadow: isDark
                        ? '0 12px 40px rgba(6, 182, 212, 0.5)'
                        : '0 12px 40px rgba(14, 165, 233, 0.4)',
                    },
                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                  }}
                >
                  Open Dashboard
                </Button>
              </motion.div>
              <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                <Button
                  variant="outlined"
                  size="large"
                  onClick={() => navigate('/live-analysis')}
                  startIcon={<Camera weight="bold" />}
                  sx={{
                    px: 4,
                    py: 1.75,
                    borderRadius: 3,
                    fontSize: '1rem',
                    fontWeight: 600,
                    borderColor: isDark 
                      ? alpha(theme.palette.primary.main, 0.5)
                      : alpha(theme.palette.primary.main, 0.3),
                    color: theme.palette.primary.main,
                    borderWidth: 2,
                    '&:hover': {
                      borderColor: theme.palette.primary.main,
                      backgroundColor: alpha(theme.palette.primary.main, 0.08),
                      borderWidth: 2,
                    },
                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                  }}
                >
                  View Live Feed
                </Button>
              </motion.div>
            </Box>
          </Box>
        </motion.div>

        {/* Stats Section - Smaller, More Compact */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2 }}
        >
          <Grid container spacing={3} sx={{ maxWidth: '900px', mx: 'auto', mb: 8 }}>
            {[
              { 
                value: stats.detections, 
                label: 'Total Detections', 
                icon: Eye, 
                color: 'primary',
                path: '/detections',
                description: 'Objects detected across all cameras'
              },
              { 
                value: stats.cameras, 
                label: 'Active Cameras', 
                icon: Camera, 
                color: 'success',
                path: '/live-analysis',
                description: 'Live camera feeds monitoring'
              },
              { 
                value: stats.uptime, 
                label: 'System Uptime', 
                icon: Pulse, 
                color: 'info',
                path: '/dashboard',
                suffix: '%',
                description: 'System reliability metric'
              },
            ].map((stat, index) => (
              <Grid item xs={12} sm={4} key={index}>
                <motion.div
                  whileHover={{ y: -8 }}
                  onHoverStart={() => setHoveredStat(index)}
                  onHoverEnd={() => setHoveredStat(null)}
                  transition={{ type: "spring", stiffness: 300 }}
                >
                  <Box
                    sx={{
                      textAlign: 'center',
                      p: 3,
                      borderRadius: 3,
                      background: isDark
                        ? alpha(theme.palette.background.paper, 0.03)
                        : 'rgba(255, 255, 255, 0.9)',
                      backdropFilter: 'blur(20px)',
                      border: `1px solid ${alpha(theme.palette[stat.color].main, 0.2)}`,
                      cursor: 'pointer',
                      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                      position: 'relative',
                      overflow: 'hidden',
                      '&:hover': {
                        boxShadow: `0 20px 40px ${alpha(theme.palette[stat.color].main, 0.2)}`,
                        border: `1px solid ${alpha(theme.palette[stat.color].main, 0.4)}`,
                      },
                    }}
                    onClick={() => navigate(stat.path)}
                  >
                    <motion.div
                      animate={hoveredStat === index ? { scale: [1, 1.2, 1] } : {}}
                      transition={{ duration: 0.5 }}
                    >
                      <stat.icon 
                        size={36} 
                        color={theme.palette[stat.color].main} 
                        weight="duotone" 
                      />
                    </motion.div>
                    <Typography 
                      variant="h4" 
                      sx={{ 
                        mt: 2, 
                        mb: 0.5, 
                        fontWeight: 800,
                        color: theme.palette[stat.color].main,
                      }}
                    >
                      {loading ? (
                        <Skeleton width={80} height={40} sx={{ mx: 'auto' }} />
                      ) : (
                        <>
                          <AnimatedNumber value={stat.value} />
                          {stat.suffix}
                        </>
                      )}
                    </Typography>
                    <Typography 
                      variant="body1" 
                      sx={{
                        color: theme.palette.text.primary,
                        fontWeight: 600,
                        mb: 0.5,
                      }}
                    >
                      {stat.label}
                    </Typography>
                    <AnimatePresence>
                      {hoveredStat === index && (
                        <motion.div
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: 10 }}
                          transition={{ duration: 0.2 }}
                        >
                          <Typography 
                            variant="caption" 
                            sx={{
                              color: isDark 
                                ? alpha(theme.palette.common.white, 0.5)
                                : alpha(theme.palette.common.black, 0.7),
                              fontSize: '0.75rem',
                            }}
                          >
                            {stat.description}
                          </Typography>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </Box>
                </motion.div>
              </Grid>
            ))}
          </Grid>
        </motion.div>

        {/* Features Grid - More Modern Layout */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.4 }}
        >
          <Typography
            variant="h4"
            sx={{
              textAlign: 'center',
              mb: 6,
              fontWeight: 700,
              color: theme.palette.text.primary,
            }}
          >
            Powerful Features
          </Typography>
          <Grid container spacing={4} sx={{ maxWidth: '1200px', mx: 'auto' }}>
            {[
              { 
                icon: <Detective weight="duotone" />, 
                title: 'Object Detection', 
                desc: 'YOLO-powered real-time detection with high accuracy', 
                path: '/live-analysis',
                color: 'primary',
                features: ['Person Detection', 'Vehicle Recognition', 'Animal Detection']
              },
              { 
                icon: <ChartLine weight="duotone" />, 
                title: 'Analytics Dashboard', 
                desc: 'Comprehensive insights and detection patterns', 
                path: '/dashboard',
                color: 'success',
                features: ['Real-time Stats', 'Historical Data', 'Export Reports']
              },
              { 
                icon: <Scan weight="duotone" />, 
                title: 'Smart Monitoring', 
                desc: 'Intelligent alerts and automated tracking', 
                path: '/detections',
                color: 'warning',
                features: ['Motion Alerts', 'Zone Monitoring', 'Event History']
              },
            ].map((feature, index) => (
              <Grid item xs={12} md={4} key={index}>
                <motion.div
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  transition={{ type: "spring", stiffness: 300 }}
                >
                  <Box
                    onClick={() => navigate(feature.path)}
                    sx={{
                      p: 4,
                      height: '100%',
                      borderRadius: 3,
                      background: isDark
                        ? alpha(theme.palette.background.paper, 0.03)
                        : 'rgba(255, 255, 255, 0.95)',
                      backdropFilter: 'blur(10px)',
                      border: `1px solid ${alpha(theme.palette.divider, isDark ? 0.1 : 0.2)}`,
                      cursor: 'pointer',
                      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                      position: 'relative',
                      overflow: 'hidden',
                      '&:hover': {
                        borderColor: alpha(theme.palette[feature.color].main, 0.4),
                        boxShadow: `0 10px 30px ${alpha(theme.palette[feature.color].main, 0.15)}`,
                        '& .feature-icon': {
                          transform: 'scale(1.1) rotate(5deg)',
                        },
                      },
                    }}
                  >
                    <Box 
                      className="feature-icon"
                      sx={{ 
                        color: theme.palette[feature.color].main,
                        mb: 3,
                        transition: 'all 0.3s ease',
                      }}
                    >
                      {React.cloneElement(feature.icon, { size: 48 })}
                    </Box>
                    <Typography 
                      variant="h5" 
                      sx={{ 
                        mb: 2, 
                        fontWeight: 700,
                        color: theme.palette.text.primary,
                      }}
                    >
                      {feature.title}
                    </Typography>
                    <Typography 
                      variant="body2" 
                      sx={{
                        color: isDark
                          ? alpha(theme.palette.common.white, 0.6)
                          : alpha(theme.palette.common.black, 0.7),
                        lineHeight: 1.6,
                        mb: 3,
                      }}
                    >
                      {feature.desc}
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                      {feature.features.map((item, i) => (
                        <Box
                          key={i}
                          sx={{
                            px: 2,
                            py: 0.5,
                            borderRadius: 2,
                            fontSize: '0.75rem',
                            background: alpha(theme.palette[feature.color].main, 0.1),
                            color: theme.palette[feature.color].main,
                            fontWeight: 500,
                          }}
                        >
                          {item}
                        </Box>
                      ))}
                    </Box>
                  </Box>
                </motion.div>
              </Grid>
            ))}
          </Grid>
        </motion.div>
      </Container>
    </Box>
  );
};

export default Home;