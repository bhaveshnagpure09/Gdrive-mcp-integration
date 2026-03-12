"use client";
import { useState } from "react";
import Topbar from "@/components/Topbar";
import { Card, Button, Input, Badge, Alert } from "@/components/ui";
import { api, BulkUpsertRequest, BulkUpsertResponse } from "@/lib/api";
import { formatMonths } from "@/lib/utils";
import { Plus, X, Upload, CheckCircle2 } from "lucide-react";

interface SkillRow {
  skill_id: string;
  skill_name: string;
  rating: string;
  experience_in_months: string;
  category: string;
}

interface AllocRow {
  project_id: string;
  allocation_percentage: string;
  start_date: string;
  end_date: string;
  billable: boolean;
}

const EMPTY_MEMBER = {
  team_member_id: "",
  full_name: "",
  team_member_status: "active" as const,
  experience_in_months: "",
  designation: "",
  profile_type: "",
  base_location: "",
  work_type: "",
  skills: [] as SkillRow[],
  allocations: [] as AllocRow[],
};

export default function TeamMembersPage() {
  const [members, setMembers] = useState([{ ...EMPTY_MEMBER }]);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<BulkUpsertResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedMember, setExpandedMember] = useState<number>(0);

  const updateMember = (idx: number, key: string, value: unknown) => {
    setMembers((prev) => prev.map((m, i) => (i === idx ? { ...m, [key]: value } : m)));
  };

  const addSkill = (idx: number) => {
    setMembers((prev) =>
      prev.map((m, i) =>
        i === idx
          ? {
              ...m,
              skills: [
                ...m.skills,
                { skill_id: `skill-${Date.now()}`, skill_name: "", rating: "5", experience_in_months: "12", category: "" },
              ],
            }
          : m
      )
    );
  };

  const updateSkill = (mIdx: number, sIdx: number, key: keyof SkillRow, value: string) => {
    setMembers((prev) =>
      prev.map((m, i) =>
        i === mIdx
          ? { ...m, skills: m.skills.map((s, j) => (j === sIdx ? { ...s, [key]: value } : s)) }
          : m
      )
    );
  };

  const removeSkill = (mIdx: number, sIdx: number) => {
    setMembers((prev) =>
      prev.map((m, i) =>
        i === mIdx ? { ...m, skills: m.skills.filter((_, j) => j !== sIdx) } : m
      )
    );
  };

  const addAlloc = (idx: number) => {
    setMembers((prev) =>
      prev.map((m, i) =>
        i === idx
          ? {
              ...m,
              allocations: [
                ...m.allocations,
                { project_id: "", allocation_percentage: "100", start_date: "", end_date: "", billable: true },
              ],
            }
          : m
      )
    );
  };

  const updateAlloc = (mIdx: number, aIdx: number, key: keyof AllocRow, value: string | boolean) => {
    setMembers((prev) =>
      prev.map((m, i) =>
        i === mIdx
          ? { ...m, allocations: m.allocations.map((a, j) => (j === aIdx ? { ...a, [key]: value } : a)) }
          : m
      )
    );
  };

  const removeAlloc = (mIdx: number, aIdx: number) => {
    setMembers((prev) =>
      prev.map((m, i) =>
        i === mIdx ? { ...m, allocations: m.allocations.filter((_, j) => j !== aIdx) } : m
      )
    );
  };

  const handleSubmit = async () => {
    setError(null);
    setSubmitting(true);
    try {
      const payload: BulkUpsertRequest = {
        metadata: {
          batch_id: `batch-${Date.now()}`,
          timestamp: new Date().toISOString(),
          total_records: members.length,
          batch_number: 1,
          total_batches: 1,
          records_in_batch: members.length,
          source_system: "ib-skill-mapper-ui",
          schema_version: "1.0",
          status: { code: 200, key: "SUCCESS", message: "OK" },
        },
        team_members: members.map((m) => ({
          team_member_id: m.team_member_id,
          full_name: m.full_name,
          team_member_status: m.team_member_status,
          experience_in_months: Number(m.experience_in_months) || 0,
          designation: m.designation || undefined,
          profile_type: m.profile_type || undefined,
          base_location: m.base_location || undefined,
          work_type: m.work_type || undefined,
          skills: m.skills
            .filter((s) => s.skill_name)
            .map((s) => ({
              skill_id: s.skill_id,
              skill_name: s.skill_name,
              rating: s.rating ? Number(s.rating) : undefined,
              experience_in_months: s.experience_in_months ? Number(s.experience_in_months) : undefined,
              category: s.category || undefined,
            })),
          allocations: m.allocations
            .filter((a) => a.project_id)
            .map((a) => ({
              project_id: a.project_id,
              allocation_percentage: a.allocation_percentage ? Number(a.allocation_percentage) : undefined,
              start_date: a.start_date || undefined,
              end_date: a.end_date || undefined,
              billable: a.billable,
            })),
        })),
      };
      const res = await api.teamMembers.bulkUpsert(payload);
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to sync team members");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <Topbar title="Team Members" />
      <div className="p-6 space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-800">Skill Availability Sync</h2>
            <p className="text-xs text-slate-500">Add team members with their skills and project allocations</p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setMembers((p) => [...p, { ...EMPTY_MEMBER }])}
            >
              <Plus className="h-3.5 w-3.5" /> Add Member
            </Button>
            <Button onClick={handleSubmit} loading={submitting} size="sm">
              <Upload className="h-3.5 w-3.5" /> Sync to API
            </Button>
          </div>
        </div>

        {error && <Alert type="error">{error}</Alert>}

        {result && (
          <Alert type="success">
            <div className="flex items-start gap-2">
              <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" />
              <div>
                <strong>Sync successful!</strong>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs">
                  <span>Members: +{result.summary.team_members_inserted} / ↻{result.summary.team_members_updated}</span>
                  <span>Skills: +{result.summary.skills_inserted} / ↻{result.summary.skills_updated}</span>
                  <span>Allocations: +{result.summary.allocations_inserted} / ↻{result.summary.allocations_updated}</span>
                  {result.summary.records_failed > 0 && (
                    <span className="text-red-600">Failed: {result.summary.records_failed}</span>
                  )}
                </div>
              </div>
            </div>
          </Alert>
        )}

        <div className="space-y-4">
          {members.map((member, mIdx) => (
            <Card key={mIdx} className="overflow-hidden">
              {/* Header */}
              <div
                className="flex cursor-pointer items-center justify-between p-4 hover:bg-slate-50 transition-colors"
                onClick={() => setExpandedMember(expandedMember === mIdx ? -1 : mIdx)}
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-violet-100 text-xs font-bold text-violet-700">
                    {mIdx + 1}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-800">
                      {member.full_name || `Member ${mIdx + 1}`}
                    </p>
                    <p className="text-xs text-slate-500">
                      ID: {member.team_member_id || "—"} · {member.skills.length} skill(s) · {member.allocations.length} allocation(s)
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={member.team_member_status === "active" ? "success" : "warning"}>
                    {member.team_member_status}
                  </Badge>
                  {member.experience_in_months && (
                    <Badge variant="info">{formatMonths(Number(member.experience_in_months))}</Badge>
                  )}
                  {members.length > 1 && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setMembers((p) => p.filter((_, i) => i !== mIdx));
                      }}
                      className="ml-2 rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-500"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>

              {expandedMember === mIdx && (
                <div className="border-t border-slate-100 p-5 space-y-5">
                  {/* Basic Info */}
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    <Input
                      label="Team Member ID *"
                      required
                      value={member.team_member_id}
                      onChange={(e) => updateMember(mIdx, "team_member_id", e.target.value)}
                      placeholder="emp_001"
                    />
                    <Input
                      label="Full Name *"
                      required
                      value={member.full_name}
                      onChange={(e) => updateMember(mIdx, "full_name", e.target.value)}
                      placeholder="John Doe"
                    />
                    <Input
                      label="Experience (months) *"
                      type="number"
                      min="0"
                      required
                      value={member.experience_in_months}
                      onChange={(e) => updateMember(mIdx, "experience_in_months", e.target.value)}
                      placeholder="36"
                    />
                    <div className="space-y-1">
                      <label className="block text-sm font-medium text-slate-700">Status</label>
                      <select
                        value={member.team_member_status}
                        onChange={(e) => updateMember(mIdx, "team_member_status", e.target.value)}
                        className="block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                      >
                        <option value="active">Active</option>
                        <option value="inactive">Inactive</option>
                        <option value="terminated">Terminated</option>
                      </select>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    <Input label="Designation" value={member.designation} onChange={(e) => updateMember(mIdx, "designation", e.target.value)} placeholder="Senior Engineer" />
                    <Input label="Profile Type" value={member.profile_type} onChange={(e) => updateMember(mIdx, "profile_type", e.target.value)} placeholder="Technical" />
                    <Input label="Base Location" value={member.base_location} onChange={(e) => updateMember(mIdx, "base_location", e.target.value)} placeholder="Indore" />
                    <Input label="Work Type" value={member.work_type} onChange={(e) => updateMember(mIdx, "work_type", e.target.value)} placeholder="Hybrid" />
                  </div>

                  {/* Skills */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-sm font-semibold text-slate-700">Skills</label>
                      <Button type="button" size="sm" variant="outline" onClick={() => addSkill(mIdx)}>
                        <Plus className="h-3.5 w-3.5" /> Add Skill
                      </Button>
                    </div>
                    {member.skills.length > 0 && (
                      <div className="rounded-lg border border-slate-200 overflow-hidden">
                        <table className="w-full text-sm">
                          <thead className="bg-slate-50">
                            <tr>
                              <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Skill Name</th>
                              <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Category</th>
                              <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Rating (1-10)</th>
                              <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Exp (months)</th>
                              <th className="w-8" />
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {member.skills.map((sk, sIdx) => (
                              <tr key={sIdx}>
                                <td className="px-3 py-2">
                                  <input
                                    className="w-full rounded border border-slate-200 px-2 py-1 text-xs focus:border-indigo-400 focus:outline-none"
                                    value={sk.skill_name}
                                    onChange={(e) => updateSkill(mIdx, sIdx, "skill_name", e.target.value)}
                                    placeholder="React"
                                  />
                                </td>
                                <td className="px-3 py-2">
                                  <input className="w-full rounded border border-slate-200 px-2 py-1 text-xs focus:border-indigo-400 focus:outline-none" value={sk.category} onChange={(e) => updateSkill(mIdx, sIdx, "category", e.target.value)} placeholder="Frontend" />
                                </td>
                                <td className="px-3 py-2">
                                  <input type="number" min="1" max="10" className="w-20 rounded border border-slate-200 px-2 py-1 text-xs focus:border-indigo-400 focus:outline-none" value={sk.rating} onChange={(e) => updateSkill(mIdx, sIdx, "rating", e.target.value)} />
                                </td>
                                <td className="px-3 py-2">
                                  <input type="number" min="0" className="w-20 rounded border border-slate-200 px-2 py-1 text-xs focus:border-indigo-400 focus:outline-none" value={sk.experience_in_months} onChange={(e) => updateSkill(mIdx, sIdx, "experience_in_months", e.target.value)} />
                                </td>
                                <td className="px-3 py-2">
                                  <button onClick={() => removeSkill(mIdx, sIdx)} className="rounded p-1 text-slate-400 hover:text-red-500">
                                    <X className="h-3.5 w-3.5" />
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                  {/* Allocations */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-sm font-semibold text-slate-700">Project Allocations</label>
                      <Button type="button" size="sm" variant="outline" onClick={() => addAlloc(mIdx)}>
                        <Plus className="h-3.5 w-3.5" /> Add Allocation
                      </Button>
                    </div>
                    {member.allocations.length > 0 && (
                      <div className="rounded-lg border border-slate-200 overflow-hidden">
                        <table className="w-full text-sm">
                          <thead className="bg-slate-50">
                            <tr>
                              <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Project ID</th>
                              <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Allocation %</th>
                              <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Start Date</th>
                              <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">End Date</th>
                              <th className="px-3 py-2 text-xs font-medium text-slate-600">Billable</th>
                              <th className="w-8" />
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {member.allocations.map((al, aIdx) => (
                              <tr key={aIdx}>
                                <td className="px-3 py-2">
                                  <input className="w-full rounded border border-slate-200 px-2 py-1 text-xs focus:border-indigo-400 focus:outline-none" value={al.project_id} onChange={(e) => updateAlloc(mIdx, aIdx, "project_id", e.target.value)} placeholder="PROJ-001" />
                                </td>
                                <td className="px-3 py-2">
                                  <input type="number" min="0" max="100" className="w-20 rounded border border-slate-200 px-2 py-1 text-xs focus:border-indigo-400 focus:outline-none" value={al.allocation_percentage} onChange={(e) => updateAlloc(mIdx, aIdx, "allocation_percentage", e.target.value)} />
                                </td>
                                <td className="px-3 py-2">
                                  <input type="date" className="rounded border border-slate-200 px-2 py-1 text-xs focus:border-indigo-400 focus:outline-none" value={al.start_date} onChange={(e) => updateAlloc(mIdx, aIdx, "start_date", e.target.value)} />
                                </td>
                                <td className="px-3 py-2">
                                  <input type="date" className="rounded border border-slate-200 px-2 py-1 text-xs focus:border-indigo-400 focus:outline-none" value={al.end_date} onChange={(e) => updateAlloc(mIdx, aIdx, "end_date", e.target.value)} />
                                </td>
                                <td className="px-3 py-2 text-center">
                                  <input type="checkbox" checked={al.billable} onChange={(e) => updateAlloc(mIdx, aIdx, "billable", e.target.checked)} className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
                                </td>
                                <td className="px-3 py-2">
                                  <button onClick={() => removeAlloc(mIdx, aIdx)} className="rounded p-1 text-slate-400 hover:text-red-500">
                                    <X className="h-3.5 w-3.5" />
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </Card>
          ))}
        </div>
      </div>
    </>
  );
}
