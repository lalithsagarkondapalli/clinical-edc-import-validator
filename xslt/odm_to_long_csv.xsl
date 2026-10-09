<?xml version="1.0" encoding="UTF-8"?>
<!--
  Flattens an ODM 1.3.2 ClinicalData snapshot into one CSV row per ItemData.
  Used for (1) an independent round-trip reconciliation and (2) the staging-table load
  (SQLite in CI, SQL*Loader on Oracle - see sql/).
-->
<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:odm="http://www.cdisc.org/ns/odm/v1.3">
  <xsl:output method="text" encoding="UTF-8"/>
  <xsl:strip-space elements="*"/>

  <xsl:template match="/">
    <xsl:text>STUDYOID,SUBJECTKEY,SITEOID,STUDYEVENTOID,FORMOID,ITEMGROUPOID,ITEMGROUPREPEATKEY,ITEMOID,VALUE&#10;</xsl:text>
    <xsl:apply-templates select="//odm:ItemData"/>
  </xsl:template>

  <xsl:template match="odm:ItemData">
    <xsl:value-of select="ancestor::odm:ClinicalData/@StudyOID"/><xsl:text>,</xsl:text>
    <xsl:value-of select="ancestor::odm:SubjectData/@SubjectKey"/><xsl:text>,</xsl:text>
    <xsl:value-of select="ancestor::odm:SubjectData/odm:SiteRef/@LocationOID"/><xsl:text>,</xsl:text>
    <xsl:value-of select="ancestor::odm:StudyEventData/@StudyEventOID"/><xsl:text>,</xsl:text>
    <xsl:value-of select="ancestor::odm:FormData/@FormOID"/><xsl:text>,</xsl:text>
    <xsl:value-of select="../@ItemGroupOID"/><xsl:text>,</xsl:text>
    <xsl:value-of select="../@ItemGroupRepeatKey"/><xsl:text>,</xsl:text>
    <xsl:value-of select="@ItemOID"/><xsl:text>,</xsl:text>
    <!-- quote the value; double any embedded quotes (RFC 4180) -->
    <xsl:text>"</xsl:text>
    <xsl:call-template name="escape"><xsl:with-param name="s" select="@Value"/></xsl:call-template>
    <xsl:text>"&#10;</xsl:text>
  </xsl:template>

  <xsl:template name="escape">
    <xsl:param name="s"/>
    <xsl:choose>
      <xsl:when test="contains($s, '&quot;')">
        <xsl:value-of select="substring-before($s, '&quot;')"/><xsl:text>""</xsl:text>
        <xsl:call-template name="escape"><xsl:with-param name="s" select="substring-after($s, '&quot;')"/></xsl:call-template>
      </xsl:when>
      <xsl:otherwise><xsl:value-of select="$s"/></xsl:otherwise>
    </xsl:choose>
  </xsl:template>
</xsl:stylesheet>
